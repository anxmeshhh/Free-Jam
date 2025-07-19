# Free Jam Setup Guide

## 🚀 Quick Setup

### 1. Install Dependencies
\\\`bash
pip install -r requirements.txt
\\\`

### 2. Get YouTube API Key
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable *YouTube Data API v3*
4. Create credentials (API Key)
5. Copy your API key

### 3. Set Environment Variable
*Windows:*
\\\`bash
set YOUTUBE_API_KEY=your_api_key_here
\\\`

*Mac/Linux:*
\\\`bash
export YOUTUBE_API_KEY=your_api_key_here
\\\`

**Or create a .env file:**
\\\`
YOUTUBE_API_KEY=your_api_key_here
\\\`

### 4. Initialize Database
\\\`bash
python scripts/setup_database.py
\\\`

### 5. Run the App
\\\`bash
python app.py
\\\`

### 6. Open Browser
Visit: http://localhost:5000

## 🎵 How It Works

1. *Search*: Users search for songs using real YouTube search
2. *Add*: Songs are added to room playlists instantly
3. *Play*: YouTube Player API streams songs directly
4. *Sync*: All users hear the same song at the same time

## 🔧 Features

- ✅ Real YouTube search integration
- ✅ Synchronized playback across all users
- ✅ Real-time room collaboration
- ✅ No downloads required
- ✅ Mobile responsive design
- ✅ Private/public rooms with PIN protection

## 🛠 Troubleshooting

*No search results?*
- Check if YouTube API key is set correctly
- Verify API key has YouTube Data API v3 enabled
- Check API quotas in Google Cloud Console

*Songs not playing?*
- Ensure YouTube Player API is loaded
- Check browser console for errors
- Some videos may be restricted

*Sync issues?*
- Check network connection
- Refresh the page
- Ensure all users are in the same room

## 🔑 YouTube API Setup (Detailed)

### Step 1: Google Cloud Console
1. Visit [console.cloud.google.com](https://console.cloud.google.com/)
2. Sign in with your Google account
3. Create a new project:
   - Click "Select a project" → "New Project"
   - Name: "Free Jam" (or any name)
   - Click "Create"

### Step 2: Enable YouTube Data API
1. In the left sidebar, click "APIs & Services" → "Library"
2. Search for "YouTube Data API v3"
3. Click on it and press "Enable"

### Step 3: Create API Key
1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "API Key"
3. Copy the generated API key
4. (Optional) Click "Restrict Key" to limit usage

### Step 4: Set API Key
Replace YOUR_YOUTUBE_API_KEY_HERE in the environment variable with your actual key.

## 📊 API Quotas

YouTube Data API has daily quotas:
- *Free tier*: 10,000 units/day
- *Search operation*: ~100 units per search
- *Video details*: ~1 unit per video

This allows for ~100 searches per day on free tier.

## 🎯 Production Deployment

For production deployment:
1. Set YOUTUBE_API_KEY environment variable on your server
2. Use a production WSGI server like Gunicorn
3. Set up SSL/HTTPS for secure connections
4. Consider using Redis for session storage
5. Monitor API usage and quotas

## 🔒 Security Notes

- Keep your YouTube API key secure
- Don't commit API keys to version control
- Use environment variables for sensitive data
- Consider API key restrictions in production
