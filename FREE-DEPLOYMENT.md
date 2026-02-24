# 🆓 FREE Deployment Guide - Healthcare Chatbot

## 🎯 Best FREE Options for Your Healthcare Chatbot

### Option 1: AWS EC2 Free Tier ⭐ (RECOMMENDED)
**Cost:** FREE for 12 months, then $8-10/month  
**Credibility:** ✅ Official AWS infrastructure  
**RAM:** 1GB + 4GB swap (enough for your AI models)  
**Control:** Full access

---

## 🚀 AWS EC2 Free Tier Deployment (Step-by-Step)

### Prerequisites
- AWS account (free signup)
- GitHub account (you already have)

### Step 1: Launch EC2 Instance (5 minutes)

1. **Go to AWS Console**: https://console.aws.amazon.com/ec2/
2. **Click "Launch Instance"**
3. **Configure:**
   ```
   Name: healthcare-chatbot
   AMI: Ubuntu Server 22.04 LTS (Free tier eligible)
   Instance type: t2.micro (Free tier eligible) ✅
   Key pair: Create new → Download .pem file
   ```
4. **Security Group (Important!):**
   ```
   Allow: SSH (22) - Your IP
   Allow: HTTP (80) - 0.0.0.0/0
   Allow: HTTPS (443) - 0.0.0.0/0
   Allow: Custom TCP (8000) - 0.0.0.0/0
   ```
5. **Storage:** 30GB gp2 (Free tier eligible) ✅
6. **Click "Launch Instance"**

### Step 2: Connect to Your Server

**Windows (PowerShell):**
```powershell
# Convert .pem to correct permissions
icacls your-key.pem /inheritance:r
icacls your-key.pem /grant:r "$env:USERNAME:(R)"

# SSH to instance
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

**Mac/Linux:**
```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

### Step 3: One-Command Setup 🎉

Once connected to EC2, run:

```bash
# Download and run setup script
curl -fsSL https://raw.githubusercontent.com/PratyushSowrirajan/deepblue-CMC-chatbot/main/setup-ec2.sh -o setup.sh
chmod +x setup.sh
./setup.sh
```

**The script will:**
- ✅ Install Docker & Docker Compose
- ✅ Create 4GB swap file (critical for 1GB RAM)
- ✅ Install Nginx reverse proxy
- ✅ Clone your repository
- ✅ Build and run container
- ✅ Configure auto-restart on reboot

**When prompted, enter your Cerebras API key.**

### Step 4: Access Your API

After setup completes (~10 minutes):

```
Your API: http://<EC2-PUBLIC-IP>
API Docs: http://<EC2-PUBLIC-IP>/docs
Health Check: http://<EC2-PUBLIC-IP>/health
```

---

## 🔧 Manual Setup (If Script Fails)

<details>
<summary>Click to expand manual steps</summary>

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# 3. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. Create swap (IMPORTANT!)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Logout and login again
exit
# SSH back in

# 5. Clone repository
git clone https://github.com/PratyushSowrirajan/deepblue-CMC-chatbot.git
cd deepblue-CMC-chatbot

# 6. Create .env
nano .env
# Add: CEREBRAS_API_KEY=your_key
# Save: Ctrl+O, Enter, Ctrl+X

# 7. Build and run
docker-compose up -d --build

# 8. Check logs
docker-compose logs -f
```

</details>

---

## 🌐 Add Custom Domain (Optional - FREE)

### Using AWS Route 53 or Cloudflare

1. **Get a free domain:** Freenom.com or use existing domain
2. **Point A record to EC2 IP:**
   ```
   Type: A
   Name: api (or @)
   Value: <your-ec2-ip>
   TTL: 300
   ```
3. **Update Nginx:**
   ```bash
   sudo nano /etc/nginx/sites-available/healthcare-chatbot
   # Change: server_name <your-domain.com>;
   sudo systemctl restart nginx
   ```

### Add FREE SSL (Let's Encrypt)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Get SSL certificate (FREE)
sudo certbot --nginx -d your-domain.com

# Auto-renews every 90 days
```

Now accessible at: `https://your-domain.com` 🔒

---

## 📊 Alternative FREE Options

### Option 2: Google Cloud Run (Better Free Tier than AWS Lambda)

**Free Tier:**
- 2 million requests/month
- 360,000 GB-seconds/month
- No credit card for first 90 days

**Pros:**
- Better free tier than AWS
- Auto-scaling
- Managed service

**Cons:**
- Cold starts (slower first request)
- 2GB RAM limit on free tier
- Not AWS (less "credibility")

**Quick Deploy:**
```bash
# Build for Cloud Run
docker build -t gcr.io/YOUR_PROJECT/healthcare-chatbot .

# Push to Google Container Registry
docker push gcr.io/YOUR_PROJECT/healthcare-chatbot

# Deploy
gcloud run deploy healthcare-chatbot \
  --image gcr.io/YOUR_PROJECT/healthcare-chatbot \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Option 3: Render.com (Easiest, but Limited)

**Free Tier:**
- 512MB RAM (too small for PyTorch)
- Spins down after 15min inactivity
- Free SSL

**Verdict:** ❌ Not recommended (insufficient RAM for AI models)

### Option 4: Fly.io

**Free Tier:**
- 3 shared-cpu-1x VMs
- 256MB RAM each
- 3GB storage total

**Verdict:** ❌ Too limited for your use case

---

## 💰 Cost Comparison (After Free Tier Expires)

| Platform | Free Duration | Cost After Free |
|----------|---------------|-----------------|
| **AWS EC2 t2.micro** | 12 months | $8-10/month |
| **Google Cloud Run** | Forever (with limits) | $0-5/month (light usage) |
| **AWS App Runner** | No free tier | $25-50/month |
| **Render.com** | Forever | $7/month (512MB) or $25 (2GB) |

---

## 🎯 Recommended Path

### Stage 1: Development (Now)
**Use:** AWS EC2 Free Tier  
**Duration:** 12 months FREE  
**Why:** Learn AWS, full control, good credibility

### Stage 2: After Free Tier (Month 13+)
**Options:**
1. **Keep EC2** - $8-10/month (if you like control)
2. **Switch to Google Cloud Run** - $0-5/month (if you want cheaper)
3. **Upgrade to App Runner** - $25-50/month (if you need scaling)

---

## 🔍 Monitoring Your Free Tier Usage

**AWS Console Dashboard:**
```
AWS Console → Billing → Free Tier
```

**Alerts:**
Set up billing alerts at $5, $10 to avoid surprises.

**EC2 Free Tier Limits:**
- 750 hours/month = 24/7 for ONE t2.micro
- 30GB EBS storage
- Don't launch multiple instances (uses hours faster)

---

## 🛠️ Useful Commands

```bash
# SSH to EC2
ssh -i your-key.pem ubuntu@<EC2-IP>

# Check container status
docker-compose ps

# View logs
docker-compose logs -f

# Restart container
docker-compose restart

# Update code
git pull
docker-compose up -d --build

# Check RAM usage
free -h

# Check disk space
df -h

# Stop everything
docker-compose down
```

---

## ⚠️ Important Notes

1. **Swap is critical:** 1GB RAM isn't enough for PyTorch without swap
2. **First request is slow:** Model loading takes 30-60 seconds
3. **Keep instance running:** Stopping/starting changes public IP (unless you use Elastic IP - $0 while running, $0.005/hour when stopped)
4. **Security:** Use security groups properly, don't expose unnecessary ports
5. **Backups:** Container data is ephemeral - persistent data needs EBS volumes

---

## 🆘 Troubleshooting

### Container crashes (Out of Memory)
```bash
# Check memory
free -h
# Ensure swap is active (should show 4GB)

# Reduce workers
# In docker-compose.yml:
# command: uvicorn app.main:app --host 0.0.0.0 --workers 1
```

### Can't connect to API
```bash
# Check if container is running
docker-compose ps

# Check EC2 security group allows port 80/8000
# Check nginx status
sudo systemctl status nginx
```

### Models not loading
```bash
# Check logs
docker-compose logs | grep -i error

# Might need to pre-download models (increases startup time)
```

---

## 📈 Next Steps

After deployment:
1. Test all endpoints with Postman
2. Monitor RAM/CPU usage
3. Set up CloudWatch alarms (free tier)
4. Connect your Android app
5. Collect user feedback

---

## 💡 Pro Tips

1. **Use Elastic IP (FREE while running):**
   - Prevents IP change on reboot
   - AWS Console → EC2 → Elastic IPs → Allocate

2. **Auto-start on boot:**
   ```bash
   crontab -e
   # Add: @reboot cd /home/ubuntu/deepblue-CMC-chatbot && docker-compose up -d
   ```

3. **Monitor costs:**
   ```bash
   # Install AWS CLI
   sudo apt install awscli
   aws configure
   aws ce get-cost-and-usage --time-period Start=2026-02-01,End=2026-02-28 --granularity MONTHLY --metrics BlendedCost
   ```

---

## 🎉 Summary

**Best FREE option:** AWS EC2 t2.micro + swap  
**Setup time:** 15 minutes  
**Cost:** FREE for 12 months  
**Credibility:** ✅ AWS infrastructure  
**Scalability:** Can upgrade to larger instance anytime

**Your app will be live at:** `http://<ec2-ip>` or `https://your-domain.com`

Ready to deploy? Run the setup script above! 🚀
