# Chat Frontend for TAAFT Backend

This is a simple HTML, CSS, and JavaScript frontend that connects to your deployed TAAFT backend chat API.

## Setup

1. Edit the `app.js` file and update the `API_BASE_URL` variable to point to your deployed backend.

```javascript
// Change this to your deployed backend URL
const API_BASE_URL = 'http://localhost:8000'; 
```

2. If your backend requires authentication, you'll need to modify the API calls in `app.js` to include the necessary authentication headers.

## Usage

1. You can serve these files using any simple HTTP server. For development, you can use:

   - Python:
     ```
     python -m http.server
     ```
   
   - Node.js (with http-server):
     ```
     npx http-server
     ```

2. Open your browser and navigate to the server address (typically http://localhost:8000 or http://localhost:8080).

3. Features:
   - Create a new chat session with the "New Chat" button
   - Send messages by typing in the input field and pressing Enter or clicking the Send button
   - Toggle between streaming and non-streaming responses
   - Select different AI models from the dropdown

## CORS Considerations

If you encounter CORS issues when connecting to your backend, make sure your backend allows cross-origin requests from your frontend domain. You may need to add appropriate CORS headers to your backend API responses.

## Customization

You can customize the appearance by modifying the `styles.css` file. The chat interface is designed to be responsive and should work on both desktop and mobile devices.

## Troubleshooting

- Check browser console (F12) for any error messages
- Verify that your backend API is running and accessible
- Make sure the API endpoints in the code match your backend's API routes 