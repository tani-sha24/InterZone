# InterZone

**A Zero Trust Enterprise Access Governance and Insider-Threat Risk Reduction Prototype**

InterZone is an educational cybersecurity project exploring how organizations can control cross-department access to sensitive resources. It demonstrates least-privilege access, approval workflows, temporary permissions, executive oversight, and audit logging.

> **Project status:** Early prototype (v0.1). This is a local demonstration, not a production-ready security system.

## Problem

In an organization, employees may need temporary access to resources owned by another department. Broad, permanent access increases the risk of accidental exposure, privilege misuse, and insider data leakage.

InterZone explores a more controlled approach:
- Deny cross-department access by default.
- Require a justified access request.
- Route the request through an appropriate approval workflow.
- Grant narrowly scoped, time-limited access.
- Re-check authorization whenever a protected resource is requested.
- Record access decisions and important actions in an audit trail.

## Current prototype features

- Flask application with a local SQLite database.
- Fictional demo users, departments, roles, and protected resources.
- Cross-department access request workflow.
- Manager review followed by resource-owner approval.
- Temporary read grants with 15, 30, or 60-minute durations.
- Server-side expiry checks and immediate grant revocation.
- Executive sensitive-resource request workflow with a second-executive approval step.
- Audit events for requests, approvals, denials, resource views, and revocations.
- Employee deactivation demonstration.

## Technology

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript

## Run locally on Windows

### 1. Download the project

Clone this repository or download it as a ZIP and extract it.

### 2. Open PowerShell in the project folder

The folder should contain `app.py` and `requirements.txt`.

### 3. Create a virtual environment

```powershell
py -m venv .venv
```

### 4. Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 5. Start the application

```powershell
.\.venv\Scripts\python.exe app.py
```

### 6. Open the local application

Visit http://127.0.0.1:5000 in your browser.

Keep the PowerShell window open while using the application. Press `Ctrl+C` to stop the development server.

## Suggested demo walkthrough

1. Select **Alice Morgan — Technical Junior Executive** from the demo identity selector.
2. Try to open a resource owned by another department. The request should be denied without an active grant.
3. Submit a 15-minute access request with a meaningful reason.
4. Switch to **Ben Carter — Technical Manager** and perform the manager review.
5. Switch to **Diana Lee — Design Manager** and approve the resource-owner step.
6. Switch back to Alice and try the resource again.
7. Revoke the grant from an authorized demo manager identity and test access again.
8. Switch to an executive identity, request access to a sensitive resource, and use a different executive identity for the second approval.
9. Review the audit trail.

The demo identity selector is only a testing convenience. It is not authentication.

## Conceptual security architecture

- **Policy Decision Point (PDP):** evaluates whether the current identity has permission to access a resource.
- **Policy Enforcement Point (PEP):** the protected-resource API route checks the decision before returning content.
- **Just-in-time access:** temporary grants are scoped to a user, resource, action, start time, and expiry time.
- **Default deny:** cross-department access is rejected unless an applicable active grant exists.
- **Audit trail:** important events are written to the local audit table.

## Important security limitations

This version is intentionally an early educational prototype. It must not be used to protect real company information or exposed to the public internet.

Not yet implemented:
- Real user authentication and secure account provisioning.
- Password hashing, MFA, and hardened session management.
- CSRF protection, production TLS, and production deployment configuration.
- Tamper-resistant or centralized audit logging.
- Complete configurable organization charts and dynamic department administration.
- Fine-grained read, download, edit, and export permissions.
- Production-grade approval policy administration.
- Real VLAN, firewall, or network-level enforcement.

The local demo identity switcher is not secure: anyone who can access the running app can select a demo identity. The Flask development server and built-in secret key are for local testing only.

## Roadmap

- [ ] Replace demo identity switching with secure login, password hashing, and MFA.
- [ ] Add dynamic department, employee, role, and reporting-line management.
- [ ] Make approval chains configurable by resource sensitivity and organization policy.
- [ ] Add separate view, download, edit, and export permissions.
- [ ] Add security tests for unauthorized access, self-approval, expiry, revocation, and inactive users.
- [ ] Improve audit integrity and add security event review.
- [ ] Add isolated Docker network demonstrations and later firewall-based enforcement.
- [ ] Improve documentation with architecture diagrams and verified screenshots.

## Repository safety

Do not commit local databases, virtual environments, secrets, real employee information, company documents, or credentials. The included `.gitignore` excludes common local files.

## Disclaimer

InterZone is a learning and portfolio project. It is not certified, audited, or suitable for production security enforcement.
