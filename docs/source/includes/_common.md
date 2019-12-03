# Common Specifications

## API Base URL

Base URL to every API in this documentation.

`/api`

## Status Code

The following status codes are returned by the this API.

Code | Meaning
---- | -------
200 | OK -- Request is successful.
400 | Bad Request -- Your request is invalid.
401 | Unauthorized -- Your JWT is wrong.
403 | Forbidden -- You can't access the resource.
405 | Method Not Allowed -- You tried to request API with an invalid method.
415 | Unsupported Media Type -- Content-Type in header is wrong.

## Responses

> A response should be something look like this:

```json
{
  "status": "ok"|"err",
  "message" : "HELO, EHLO"
  "data" : {
    "user": "bogay",
    "sessionId": "Y2hpa2EgdHRvIGNoaWthIGNoaWth"
  }
}
```

A common response.

### Content-Type

`application/json`

### Body

Property | Type | Description
-------- | ---- | -----------
status | String | Status of the request
message | String | Message from the server
data | JSON Object | Any data if it is required, or it will be `null`
