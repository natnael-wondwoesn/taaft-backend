# Chat API Response Format & Frontend Integration

## Overview

The non-streaming chat endpoint in `app/chat/routes.py` (`send_chat_message`) was updated to match the `ChatMessageResponse` schema. It now returns:

```json
{
  "message": "<assistant reply text>",
  "chat_id": "<session_id>",
  "message_id": "<new message id>",
  "timestamp": "2023-04-01T12:00:00Z",
  "model": "gpt4"
}
```

This aligns with the Pydantic model:

```python
class ChatMessageResponse(BaseModel):
    message: str
    chat_id: str
    message_id: str
    timestamp: datetime.datetime
    model: ChatModelType
    metadata: Optional[List[Dict[str, Any]]] = None
    tool_recommendations: Optional[List[Dict[str, Any]]] = None
```

## Frontend Integration

### Non-Streaming Example (fetch)

```javascript
async function sendMessage(sessionId, text) {
  const response = await fetch(`/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text })
  });
  if (!response.ok) {
    throw new Error(`Chat API error: ${response.statusText}`);
  }
  const { message, chat_id, message_id, timestamp, model } = await response.json();
  return { id: message_id, text: message, timestamp: new Date(timestamp), model };
}
```

### Streaming Example (EventSource)

```javascript
function subscribeToChat(sessionId, onMessage) {
  const url = `/api/chat/sessions/${sessionId}/messages/stream`;
  const source = new EventSource(url);
  source.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.event === 'chunk') {
      onMessage(data.content);
    } else if (data.event === 'end') {
      source.close();
    }
  };
  return source;
}
```

### Error Handling

- Check HTTP status codes (`4xx`, `5xx`).
- Display user-friendly messages on failures.

### Putting It All Together

1. **Create or reuse** a chat session.
2. **Call** `sendMessage(sessionId, text)` for non-streaming requests.
3. **Render** each returned message object in your chat UI.
4. **Optionally** use `subscribeToChat(...)` for streaming updates.

With this setup, your frontend will correctly consume the updated JSON shape and keep chat history in sync with the backend. 