## send-approval-email

Supabase Edge Function to send email notifications for attendance request
approvals and rejections.

### Environment Variables

Set these in Supabase Functions env:

- `RESEND_API_KEY` - API key for Resend
- `FROM_EMAIL` - Verified sender address (e.g. `noreply@yourdomain.com`)

### Payload

```
{
  "email": "user@example.com",
  "name": "User Name",
  "decision": "APPROVED|REJECTED",
  "comment": "Reason (optional)",
  "request_type": "LEAVE|WFH|SICK_LEAVE|...",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD"
}
```

