# FooDIE Restaurant Analytics — Menu & Price Tracker

Multi-restaurant menu price tracker, item analyzer, and dining analytics dashboard.

---

## 🌐 Dashboard & Live Preview

![Dashboard Preview](screenshots/dashboard.png)

---

## 📈 Price History & Historical Analytics

![Price History & Charts](screenshots/price_history.png)

---

## 🔍 Features & Interactive Exploration

![Features & Category View](screenshots/features.png)

---

## 🛠️ Features & Architecture

- **Automated Price Tracking**: Scrapes live catalog prices and logs historical deltas.
- **Fast Interactive UI**: Clean, responsive frontend with search, filters, and movers panels.
- **Automated GitHub Pipeline**: Continuous scraping and daily snapshot deployments via GitHub Actions & Kaggle orchestrator.

## ⚡ Local Run Instructions

```bash
# Run the scraper entry point
python scraper.py

# Serve dashboard locally
python -m http.server 8000
```
