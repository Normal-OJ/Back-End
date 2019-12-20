# Inbox

## Received Messages List

> Example request:

```python
print(requests.get(f'{API_BASE_URL}/inbox').json())
```

```javascript
axios.get(`${API_BASE_URL}/inbox`)
  .then(response => console.log(response.data))
  .catch(error => console.log(error.response.data));
```

> Example response:

```json
{
  "data": [
    {
      "messageId": "5dfc2fdb15f0a446e872ee3d",
      "sender": "AlaRduTP",
      "timestamp": 1576808411,
      "title": "test title",
      "message": "test msg",
      "status": 0
    }
  ],
  "message": "Received List",
  "status": "ok"
}
```

Get a list of received messages.

### HTTP Request

`GET /inbox`

### Reponse Body (data [])

Property | Type | Description
-------- | ---- | -----------
status | Number | `0` Unread / `1` Read

## Send a Message

> Example request body (DATA):

```json
{
  "receivers": [
    "test_user1",
    "test_user2"
  ],
  "title": "test title",
  "message": "test msg"
}
```

> Example request:

```python
print(requests.post(f'{API_BASE_URL}/inbox', DATA).json())
```

```javascript
axios.post(`${API_BASE_URL}/auth/session`, DATA)
  .then(response => console.log(response.data))
  .catch(error => console.log(error.response.data));
```

> Example response:

```json
{
  "data": {
    "messageId": "5dfc2fdb15f0a446e872ee3c",
    "timestamp": 1576808411,
    "receivers": [
      "test_user1",
      "test_user2"
    ]
  },
  "message": "Successfully Send",
  "status": "ok"
}
```

Send a message to users.

### HTTP Request

`POST /inbox`

### Request Body

Property | Type | Required | Description
-------- | ---- | -------- | -----------
receivers | Array | Required | A list of usernames
title | String | Required | The title of the message
message | String | Required | The body of the message

## Change Message Status

> Example request body (DATA):

```json
{
  "messageId": "5dfc2fdb15f0a446e872ee3d"
}
```

> Example request:

```python
print(requests.put(f'{API_BASE_URL}/inbox', json=DATA).json())
```

```javascript
axios.put(f`${API_BASE_URL}/inbox`, DATA)
  .then(response => console.log(response.data))
  .catch(error => console.log(error.response.data));
```

> Example response:

```json
{
  "data": {
    "status": 1
  },
  "message": "Message Status Changed",
  "status": "ok"
}
```

Change the status of a message: unread and read.

### HTTP Request

`PUT /inbox`

### Request Body

Property | Type | Required | Description
-------- | ---- | -------- | -----------
messageId | String | Required | ID of a message

### Reponse Body (data)

Property | Type | Description
-------- | ---- | -----------
status | Number | `0` Unread / `1` Read

## Delete a received Message

> Example request body (DATA):

```json
{
  "messageId": "5dfc2fdb15f0a446e872ee3d"
}
```

> Example request:

```python
print(requests.delete(f'{API_BASE_URL}/inbox', json=DATA).json())
```

```javascript
axios.delete(f`${API_BASE_URL}/inbox`, {data: DATA})
  .then(response => console.log(response.data))
  .catch(error => console.log(error.response.data));
```

> Example response:

```json
{
  "data": null,
  "message": "Deleted",
  "status": "ok"
}
```

Delete a received message.

### HTTP Request

`DELETE /inbox`

### Request Body

Property | Type | Required | Description
-------- | ---- | -------- | -----------
messageId | String | Required | ID of a message

## Sent Messages List

> Example request:

```python
print(requests.get(f'{API_BASE_URL}/inbox/sent').json())
```

```javascript
axios.get(`${API_BASE_URL}/inbox/sent`)
  .then(response => console.log(response.data))
  .catch(error => console.log(error.response.data));
```

> Example response:

```json
{
  "data": [
    {
      "messageId": "5dfc2fdb15f0a446e872ee3c",
      "receivers": [
        "test_user1",
        "test_user2"
      ],
      "timestamp": 1576808411,
      "title": "test title",
      "message": "test msg"
    }
  ],
  "message": "Sent List",
  "status": "ok"
}
```

Get a list of sent messages.

### HTTP Request

`GET /inbox/sent`

## Delete a Sent Message

> Example request body (DATA):

```json
{
  "messageId": "5dfc2fdb15f0a446e872ee3c"
}
```

> Example request:

```python
print(requests.delete(f'{API_BASE_URL}/inbox/sent', json=DATA).json())
```

```javascript
axios.delete(f`${API_BASE_URL}/inbox/sent`, {data: DATA})
  .then(response => console.log(response.data))
  .catch(error => console.log(error.response.data));
```

> Example response:

```json
{
  "data": null,
  "message": "Deleted",
  "status": "ok"
}
```

Delete a sent message.

### HTTP Request

`DELETE /inbox/sent`

### Request Body

Property | Type | Required | Description
-------- | ---- | -------- | -----------
messageId | String | Required | ID of a message
