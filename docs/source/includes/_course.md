# Course

## Login

> Example request body (DATA):

```json
{
  "username": "test",
  "password": "test",
}
```

> Example request:

```python
print(requests.post('API_BASE_URL/auth/session', json=DATA).json())
```

```javascript
axios.post('API_BASE_URL/auth/session', DATA)
  .then(response => console.log(response.data))
  .catch(error => console.log(error.response.data));
```

> Example response:

```json
{
  "data": null,
  "message": "Login Success",
  "status": "ok"
}
```

Create a session.

### HTTP Request

`POST /auth/session`

### Request Body

Property | Type | Required | Description
-------- | ---- | -------- | -----------
username | String | Required | Username or **email**
password | String | Required | Password

## Logout

> Example request:

```python
print(requests.get('API_BASE_URL/auth/session').json())
```

```javascript
axios.get('API_BASE_URL/auth/session')
  .then(response => console.log(response.data))
  .catch(error => console.log(error.response.data));
```

> Example response:

```json
{
  "data": null,
  "message": "Goodbye test",
  "status": "ok"
}
```

Close a session.

### HTTP Request

`GET /auth/session`

## Sign Up

> Example request body (DATA):

```json
{
  "username": "test",
  "password": "test",
  "email": "test@test.com"
}
```

> Example request:

```python
print(requests.post('API_BASE_URL/auth/signup', json=DATA).json())
```

```javascript
axios.post('API_BASE_URL/auth/signup', DATA)
  .then(response => console.log(response.data))
  .catch(error => console.log(error.response.data));
```

> Example response:

```json
{
  "data": null,
  "message": "Signup success",
  "status": "ok"
}
```

Create a new user.

### HTTP Request

`POST /auth/signup`

### Request Body

Property | Type | Required | Description
-------- | ---- | -------- | -----------
username | String | Required | Username
password | String | Required | Password
email | String | Required | Email

## Check

> Example request body (DATA):

```json
{
  "username": "test"
}
```

> Example request:

```python
print(requests.post('API_BASE_URL/auth/check/username', json=DATA).json())
```

```javascript
axios.post('API_BASE_URL/auth/check/username', DATA)
  .then(response => console.log(response.data))
  .catch(error => console.log(error.response.data));
```

> Example response:

```json
{
  "data": {
    "valid": 0
  },
  "message": "User exists.",
  "status": "ok"
}
```

Check items.

### HTTP Request

`POST /auth/check/<item>`

### Path Parameters

Property | Type | Required | Description
-------- | ---- | -------- | -----------
item | String | Required | `username` or `email`

### Request Body

Property | Type | Required | Description
-------- | ---- | -------- | -----------
`username` or `email` | String | Required | Username or email

### Response Data

Property | Type | Description
-------- | ---- | -----------
valid | Number | Checking result<br>`0` : Invalid<br>`1` : Valid

## Redirect to active-page

> Example request:

```python
print(requests.get('API_BASE_URL/auth/active/<token>').text)
```

```javascript
axios.get('API_BASE_URL/auth/active/<token>')
  .then(response => console.log(response.data));
```

Redirect user to active-page.

### HTTP Request

`GET /auth/active/<token>`

### Path Parameters

Property | Type | Required | Description
-------- | ---- | -------- | -----------
token | String | Required | JWT

### HTTP Status Code

`302` Found -- Redirect to active-page.

## Active

> Example request body (DATA):

```json
{
  "agreement": true,
  "profile": {
    "displayedName": "Test",
    "bio": "Hi"
  }
}
```

> Example request:

```python
print(requests.post('API_BASE_URL/auth/active', json=DATA).json())
```

```javascript
axios.post('API_BASE_URL/auth/active', DATA)
  .then(response => console.log(response.data))
  .catch(error => console.log(error.response.data));
```

> Example response:

```json
{
  "data": null,
  "message": "User is now active.",
  "status": "ok"
}
```

Verify user's email and update user's profile.

### HTTP Request

`POST /auth/active`

### Request Body

Property | Type | Required | Description
-------- | ---- | -------- | -----------
agreement | Boolean | Required | Should be `true`
profile | JSON Object | Required | User's profile

- **profile**

Property | Type | Required | Description
-------- | ---- | -------- | -----------
displayedName | String | Required | Display name
bio | String | Required | Autobiography
