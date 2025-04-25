# Chat Frontend for TAAFT Backend

This is a simple HTML, CSS, and JavaScript frontend that connects to your deployed TAAFT backend chat API.

## Setup

1. Edit the `app.js` file to update the `API_BASE_URL` variable if needed (current value set to the deployed backend):

```javascript
const API_BASE_URL = 'https://taaft-backend.onrender.com';
```

## Authentication

The application now includes a login system that:
- Authenticates with the backend using username and password
- Stores the authentication token in localStorage for session persistence
- Automatically logs in returning users
- Handles token expiration by returning to the login screen
- Provides a logout option

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

3. Login with your credentials to access the chat interface.

4. Features:
   - Login with username and password
   - Persistent sessions via localStorage
   - Create a new chat session with the "New Chat" button
   - Send messages by typing in the input field and pressing Enter or clicking the Send button
   - Toggle between streaming and non-streaming responses
   - Select different AI models from the dropdown
   - Logout functionality

## CORS Considerations

If you encounter CORS issues when connecting to your backend, make sure your backend allows cross-origin requests from your frontend domain. You may need to add appropriate CORS headers to your backend API responses.

## Security Notes

- This implementation stores the authentication token in localStorage, which is convenient but potentially vulnerable to XSS attacks.
- For production use, consider implementing additional security measures such as token refresh mechanisms and secure cookie storage.

## Customization

You can customize the appearance by modifying the `styles.css` file. The chat interface is designed to be responsive and should work on both desktop and mobile devices.

## Troubleshooting

- Check browser console (F12) for any error messages
- Verify that your backend API is running and accessible
- Make sure the API endpoints in the code match your backend's API routes
- If login fails, verify your credentials and ensure the authentication endpoint is correctly implemented on the backend 