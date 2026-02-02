import os
from typing import Optional, List

import requests


def send_attendance_request_decision_email(
    *,
    user_email: str,
    user_name: str,
    decision: str,
    comment: Optional[str],
    request_type: str,
    start_date: str,
    end_date: str,
    requester_name: Optional[str] = None,
    project_names: Optional[str] = None,
    cc_emails: Optional[List[str]] = None,
) -> None:
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_role_key:
        print(f"[EMAIL] Skipped - Missing env vars. SUPABASE_URL={bool(supabase_url)}, SERVICE_ROLE_KEY={bool(service_role_key)}")
        return

    function_url = f"{supabase_url}/functions/v1/send-approval-email"
    payload = {
        "email": user_email,
        "name": user_name,
        "decision": decision,
        "comment": comment or "",
        "request_type": request_type,
        "start_date": start_date,
        "end_date": end_date,
    }
    if cc_emails:
        payload["cc"] = cc_emails
    if requester_name:
        payload["requester_name"] = requester_name
    if project_names:
        payload["project_names"] = project_names

    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }

    print(f"[EMAIL] Sending {decision} notification to {user_email} for {request_type} request...")

    try:
        response = requests.post(function_url, json=payload, headers=headers, timeout=10)
        print(f"[EMAIL] Response: status={response.status_code}, body={response.text[:200] if response.text else 'empty'}")
    except Exception as e:
        print(f"[EMAIL] Failed to send email to {user_email}: {e}")
        return


def send_attendance_request_created_email(
    *,
    recipient_email: str,
    recipient_name: str,
    requester_name: str,
    request_type: str,
    start_date: str,
    end_date: str,
    reason: Optional[str],
    project_names: Optional[str],
) -> None:
    rpm_cc_email = os.getenv("RPM_CC_EMAIL")
    cc_emails = None
    if rpm_cc_email:
        cc_emails = [email.strip() for email in rpm_cc_email.split(",") if email.strip()]
    send_attendance_request_decision_email(
        user_email=recipient_email,
        user_name=recipient_name or recipient_email,
        decision="REQUESTED",
        comment=reason,
        request_type=request_type,
        start_date=start_date,
        end_date=end_date,
        requester_name=requester_name,
        project_names=project_names,
        cc_emails=cc_emails,
    )

