## Request Format

After receiving a cursor, the client can *continue* paginating by issuing a request
including that cursor:

```json
{
  "jsonrpc": "2.0",
  "id": "124",
  "method": "resources/list",
  "params": {
    "cursor": "eyJwYWdlIjogMn0="
  }
}
```
