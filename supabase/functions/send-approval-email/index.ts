import { serve } from "https://deno.land/std@0.192.0/http/server.ts";

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY");
const FROM_EMAIL = Deno.env.get("FROM_EMAIL");

serve(async (req) => {
  if (!RESEND_API_KEY || !FROM_EMAIL) {
    return new Response("Missing RESEND_API_KEY or FROM_EMAIL", { status: 500 });
  }

  const body = await req.json();
  const {
    email,
    name,
    decision,
    comment,
    request_type,
    start_date,
    end_date,
    requester_name,
    project_names,
  } = body;
  const projectLine = project_names
    ? `<p><strong>Projects:</strong> ${project_names}</p>`
    : "";

  let subject = "Attendance request update";
  let decisionLine = "There is an update on an attendance request.";

  if (decision === "REQUESTED") {
    subject = "New attendance request submitted";
    decisionLine = requester_name
      ? `A new attendance request was submitted by ${requester_name}.`
      : "A new attendance request was submitted.";
  } else if (decision === "APPROVED") {
    subject = "Your attendance request was approved";
    decisionLine = "Your request has been approved.";
  } else if (decision === "REJECTED") {
    subject = "Your attendance request was rejected";
    decisionLine = "Your request has been rejected.";
  }

  let commentLine = "";
  if (comment) {
    commentLine =
      decision === "REQUESTED"
        ? `<p><strong>Reason:</strong> ${comment}</p>`
        : `<p><strong>Reason:</strong> ${comment}</p>`;
  }

  const html = `
    <div style="font-family: Arial, sans-serif;">
      <p>Hi ${name},</p>
      <p>${decisionLine}</p>
      ${projectLine}
      <p><strong>Type:</strong> ${request_type}</p>
      <p><strong>Dates:</strong> ${start_date} to ${end_date}</p>
      ${commentLine}
      <p>Regards,<br/>Resource Management</p>
    </div>
  `;

  const resendResponse = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: FROM_EMAIL,
      to: email,
      subject,
      html,
    }),
  });

  if (!resendResponse.ok) {
    const error = await resendResponse.text();
    return new Response(error, { status: 500 });
  }

  return new Response("ok");
});

