import os

# Test OAuth credentials
os.environ["GOOGLE_CLIENT_ID"] = "your_test_client_id"
os.environ["GOOGLE_CLIENT_SECRET"] = "your_test_client_secret"
os.environ["GITHUB_CLIENT_ID"] = "Ov23liX181XskHiXfYQ4"
os.environ["GITHUB_CLIENT_SECRET"] = "076f6dff9ce7c161ae77ae7d1642b451805654cc"

# Test database
os.environ["MONGODB_URL"] = (
    "mongodb+srv://natnaelwondwoesn:rBBwT2s6s5YsEjsO@cluster0.0gsof12.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)

# Frontend URLs for testing
os.environ["FRONTEND_URL"] = "https://taaft-deploy-18xw.vercel.app/"
os.environ["FRONTEND_SUCCESS_URL"] = "https://taaft-deploy-18xw.vercel.app/auth/success"
os.environ["FRONTEND_ERROR_URL"] = "https://taaft-deploy-18xw.vercel.app/auth/error"

# JWT
os.environ["JWT_SECRET_KEY"] = "test_secret_key"
