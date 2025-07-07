package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"net/http/cookiejar"
	"os"
	"strconv"
	"sync"
)

// APIResponse matches the expected JSON structure for the submission list
type APIResponse struct {
	Data struct {
		Submissions []struct {
			SubmissionID string `json:"submissionId"`
		} `json:"submissions"`
	} `json:"data"`
}

// LoginRequest defines the structure for the login request body
type LoginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

const baseAPIURL = "http://localhost:8080/api"

// loginUser authenticates the user and returns an http.Client with session cookies
func loginUser(username, password string) (*http.Client, error) {
	loginURL := fmt.Sprintf("%s/auth/session", baseAPIURL)
	loginPayload := LoginRequest{Username: username, Password: password}
	payloadBytes, err := json.Marshal(loginPayload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal login payload: %w", err)
	}

	// Create a new cookie jar
	jar, err := cookiejar.New(nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create cookie jar: %w", err)
	}

	// Create an HTTP client with the cookie jar
	client := &http.Client{
		Jar: jar,
	}

	resp, err := client.Post(loginURL, "application/json", bytes.NewBuffer(payloadBytes))
	if err != nil {
		return nil, fmt.Errorf("login request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := ReadAll(resp)
		return nil, fmt.Errorf("login failed: status code %d, body: %s", resp.StatusCode, string(bodyBytes))
	}

	// Cookies are now stored in client.Jar automatically
	log.Println("Login successful, session cookies should be set.")
	return client, nil
}

// fetchSubmissionIDs retrieves submission IDs from the API using the provided http.Client
func fetchSubmissionIDs(offset, count int, client *http.Client) ([]string, error) {
	url := fmt.Sprintf("%s/submission?count=%d&offset=%d", baseAPIURL, count, offset)

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch submissions: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to fetch submissions: status code %d", resp.StatusCode)
	}

	var apiResp APIResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return nil, fmt.Errorf("failed to decode submission response: %w", err)
	}

	var ids []string
	for _, sub := range apiResp.Data.Submissions {
		ids = append(ids, sub.SubmissionID)
	}
	return ids, nil
}

// migrateSubmissionCode sends a POST request to migrate the code for a given submission ID using the provided http.Client
func migrateSubmissionCode(submissionID string, client *http.Client) {
	log.Printf("Processing submissionId: %s", submissionID)
	url := fmt.Sprintf("%s/submission/%s/migrate-code", baseAPIURL, submissionID)

	req, err := http.NewRequest("POST", url, nil)
	if err != nil {
		log.Printf("Error creating request for submissionId %s: %v", submissionID, err)
		return
	}

	resp, err := client.Do(req)
	if err != nil {
		log.Printf("Error migrating code for submissionId %s: %v", submissionID, err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent && resp.StatusCode != http.StatusAccepted {
		bodyBytes, err := ReadAll(resp)
		if err != nil {
			bodyBytes = []byte("failed to read response body")
		}
		log.Printf("Error migrating code for submissionId %s: status code %d, body: %s", submissionID, resp.StatusCode, string(bodyBytes))
		return
	}

	log.Printf("Successfully triggered migration for submissionId: %s (Status: %s)", submissionID, resp.Status)
}

// ReadAll is a helper, as ioutil.ReadAll is deprecated in Go 1.16+
// For older Go versions, use ioutil.ReadAll
func ReadAll(r *http.Response) ([]byte, error) {
	if r == nil || r.Body == nil {
		return nil, fmt.Errorf("response or response body is nil")
	}
	b := bytes.NewBuffer(make([]byte, 0, 512))
	_, err := b.ReadFrom(r.Body)
	return b.Bytes(), err
}

func main() {
	offset := flag.Int("offset", 0, "Offset for fetching submissions")
	count := flag.Int("count", 10, "Number of submissions to fetch")
	username := flag.String("username", "", "Username for login")
	password := flag.String("password", "", "Password for login")
	numConsumers := flag.Int("consumers", 5, "Number of consumer goroutines for migration")
	flag.Parse()

	if *username == "" || *password == "" {
		envUser := os.Getenv("OJ_USERNAME")
		envPass := os.Getenv("OJ_PASSWORD")
		if *username == "" {
			*username = envUser
		}
		if *password == "" {
			*password = envPass
		}
		if *username == "" || *password == "" {
			log.Fatal("Username and password must be provided either via flags (-username, -password) or environment variables (OJ_USERNAME, OJ_PASSWORD)")
		}
	}

	log.Println("Attempting to login...")
	httpClient, err := loginUser(*username, *password)
	if err != nil {
		log.Fatalf("Login failed: %v", err)
	}
	log.Println("Login successful.")

	// Positional argument parsing for offset and count (if no flags were set for them)
	args := flag.Args()
	if len(args) > 0 {
		val, err := parseInt(args[0])
		if err == nil {
			isOffsetDefault := true
			flag.Visit(func(f *flag.Flag) {
				if f.Name == "offset" {
					isOffsetDefault = false
				}
			})
			if isOffsetDefault {
				*offset = val
			}
		} else {
			log.Printf("Warning: Could not parse first positional argument as offset: %v. Using default or flag value.", err)
		}
	}
	if len(args) > 1 {
		val, err := parseInt(args[1])
		if err == nil {
			isCountDefault := true
			flag.Visit(func(f *flag.Flag) {
				if f.Name == "count" {
					isCountDefault = false
				}
			})
			if isCountDefault {
				*count = val
			}
		} else {
			log.Printf("Warning: Could not parse second positional argument as count: %v. Using default or flag value.", err)
		}
	}

	submissionIDChan := make(chan string, 1000) // Buffered channel for submission IDs
	var consumerWg sync.WaitGroup

	// Producer goroutine
	go func() {
		defer close(submissionIDChan) // Close channel when producer is done
		const chunk = 100
		fetchOffset := offset
		for *fetchOffset < *offset+*count {
			fetchCount := chunk
			if *fetchOffset+chunk > *offset+*count {
				fetchCount = *offset + *count - *fetchOffset
			}
			log.Printf("Fetching submission IDs with offset: %d, count: %d", *fetchOffset, fetchCount)
			submissionIDs, err := fetchSubmissionIDs(*fetchOffset, fetchCount, httpClient)
			if err != nil {
				log.Printf("Error fetching submission IDs: %v. Producer stopping.", err)
				return
			}

			if len(submissionIDs) == 0 {
				log.Println("No submission IDs found to process.")
				return
			}
			log.Printf("Found %d submission(s) to process. Pushing to channel.", len(submissionIDs))
			for _, id := range submissionIDs {
				submissionIDChan <- id
			}
			*fetchOffset += chunk
		}
		log.Println("Producer finished sending all submission IDs.")
	}()

	// Consumer goroutines
	log.Printf("Starting %d consumer goroutines...", *numConsumers)
	for i := 0; i < *numConsumers; i++ {
		consumerWg.Add(1)
		go func(workerID int) {
			defer consumerWg.Done()
			log.Printf("Consumer %d started", workerID)
			for id := range submissionIDChan {
				log.Printf("Consumer %d processing submissionId: %s", workerID, id)
				migrateSubmissionCode(id, httpClient)
			}
			log.Printf("Consumer %d finished.", workerID)
		}(i + 1)
	}

	consumerWg.Wait() // Wait for all consumers to finish
	log.Println("All processing finished.")
}

// Helper to parse int from string for positional arguments
func parseInt(s string) (int, error) {
	return strconv.Atoi(s)
}
