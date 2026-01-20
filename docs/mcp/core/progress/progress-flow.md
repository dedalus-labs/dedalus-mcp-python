## Progress Flow

When a party wants to *receive* progress updates for a request, it includes a
`progressToken` in the request metadata.

* Progress tokens **MUST** be a string or integer value
* Progress tokens can be chosen by the sender using any means, but **MUST** be unique
  across all active requests.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "some_method",
  "params": {
    "_meta": {
      "progressToken": "abc123"
    }
  }
}
```

The receiver **MAY** then send progress notifications containing:

* The original progress token
* The current progress value so far
* An optional "total" value
* An optional "message" value

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": {
    "progressToken": "abc123",
    "progress": 50,
    "total": 100,
    "message": "Reticulating splines..."
  }
}
```

* The `progress` value **MUST** increase with each notification, even if the total is
  unknown.
* The `progress` and the `total` values **MAY** be floating point.
* The `message` field **SHOULD** provide relevant human readable progress information.
