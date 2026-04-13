# Resend Email Setup

Admin notification emails are sent via [Resend](https://resend.com) from `notifications@gedsio.com`.

## 1. Create a Resend Account

1. Sign up at https://resend.com
2. Go to **API Keys** → Create a new key
3. Copy the key (starts with `re_`)

## 2. Verify Your Domain

1. Go to https://resend.com/domains → **Add Domain**
2. Enter `gedsio.com`
3. Resend will give you DNS records to add. Go to your domain registrar (or DNS provider) and add:

| Type | Name | Value |
|------|------|-------|
| MX | `send._domainkey.gedsio.com` | `feedback-smtp.us-east-1.amazonses.com` |
| TXT | `send._domainkey.gedsio.com` | *(Resend provides this — it's a DKIM key)* |
| TXT | `gedsio.com` | `v=spf1 include:amazonses.com ~all` *(add to existing SPF if you have one)* |

4. Click **Verify** in Resend once DNS propagates (usually 5-30 minutes)

## 3. Set Environment Variables

Add to your `.env` file:

```
RESEND_API_KEY=re_your_api_key_here
EMAIL_FROM_ADDRESS=notifications@gedsio.com
```

Both are already wired into `docker-compose.yml` and `config.py`.

## 4. Ensure Admins Have Email Addresses

Notifications are sent to all users with `is_admin=True` who have an email address set. If an admin signed up via username/password only, set their email in the admin panel or database.

## Events That Trigger Emails

| Event | When |
|-------|------|
| **New User Signup** | User registers via form or Google OAuth |
| **New Purchase** | Stripe checkout session completes (one-time or subscription) |
| **Account Paused** | Stripe subscription status changes to "paused" |
| **Service Canceled** | Stripe subscription is deleted/canceled |

## Graceful Degradation

If `RESEND_API_KEY` is not set, emails are silently skipped with a warning log. The app works normally without it.
