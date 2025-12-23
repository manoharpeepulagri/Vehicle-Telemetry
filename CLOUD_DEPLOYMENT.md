# 🌍 Cloud Deployment Guide - Railway.app

## Why Railway?
✅ **Free tier** - $5/month free credits  
✅ **Easy GitHub integration** - 1-click deploy  
✅ **Auto-deploy** - Updates on every git push  
✅ **Custom domains** - Show your domain to clients  
✅ **Persistent storage** - Logs and data retention  

---

## 📋 Step 1: Prepare Your Code

### Initialize Git (if not already done)
```bash
cd C:\Users\peepu\Downloads\Moniter
git init
git config user.email "your-email@example.com"
git config user.name "Your Name"
git add .
git commit -m "Initial commit - Vehicle Telemetry"
```

### Create GitHub Repository

1. Go to **https://github.com/new**
2. Create repo: `Vehicle-Telemetry`
3. Copy the commands shown and run:
```bash
git remote add origin https://github.com/<your-username>/Vehicle-Telemetry.git
git branch -M main
git push -u origin main
```

---

## 🚀 Step 2: Deploy to Railway

### Option A: Via Railway CLI (Fastest)

1. **Install Railway CLI:**
   ```bash
   npm install -g @railway/cli
   ```
   (Or download from: https://railway.app/cli)

2. **Login to Railway:**
   ```bash
   railway login
   ```

3. **Initialize & Deploy:**
   ```bash
   cd C:\Users\peepu\Downloads\Moniter
   railway init
   railway up
   ```

### Option B: Via Railway Dashboard (Easy GUI)

1. Go to **https://railway.app**
2. Sign up with GitHub
3. Click **"+ New Project"** → **"Deploy from GitHub Repo"**
4. Select your repository
5. Click **Deploy**
6. Railway will auto-detect `Procfile` and deploy! 🎉

---

## 🌐 Step 3: Access Your Live App

After deployment:
1. Go to Railway dashboard
2. Find your project
3. Click on your service
4. Copy the **Public URL** (looks like: `https://vehicletelemetry-prod.up.railway.app`)
5. Share worldwide! 🌍

**Example:** `https://your-app-name.railway.app/`

---

## 📊 Monitor Live

In Railway Dashboard:
- ✅ View logs in real-time
- ✅ Monitor CPU/Memory usage
- ✅ See deployment history
- ✅ Restart service anytime

---

## 🔧 Custom Domain (Optional)

1. In Railway: **Settings** → **Domain** → **+ Add Domain**
2. Point your domain DNS to Railway
3. Access at: `https://yourdomain.com` ✨

---

## 💡 Tips

### Auto-Deploy on Every Push
Once connected to GitHub, Railway automatically:
1. Detects new commits
2. Rebuilds your app
3. Deploys live (no downtime)

Just push your changes:
```bash
git add .
git commit -m "Fix UI colors"
git push
```

### Environment Variables
If you need to add secrets (API keys, etc.):
1. Railway Dashboard → Variables
2. Add: `NAME=value`
3. Auto-redeploys with new vars

### Check Logs
```bash
railway logs
```

---

## 📱 Share with Team

Once deployed, share this URL with your team:
```
https://your-app-name.railway.app
```

Anyone with the link can view live vehicle telemetry! 🚗💨

---

## ❌ Troubleshooting

### Port Issue
Railway auto-assigns `$PORT`. Already handled in `Procfile` ✅

### MQTT Connection
MQTT broker connection will work from cloud ✅  
(Your broker is internet-accessible)

### Logs Show Errors
```bash
railway logs -f  # Stream live logs
```

---

## 📞 Need Help?

- Railway Support: https://railway.app/help
- GitHub Issues: Post in your repo

---

**Your app is now accessible worldwide! 🌍🎉**
