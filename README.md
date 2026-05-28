# Vehicle Service Management System (Flask + DynamoDB)

Full-stack cloud-ready web application for vehicle service workflows.

## Features

- User authentication (register/login/logout) with hashed passwords.
- Role-based access:
  - Admin dashboard
  - Customer dashboard
- DynamoDB-only backend (no SQLite/MySQL).
- Customer features:
  - Add and view vehicles
  - Book service appointments
  - View service history
  - View invoice after completion
- Admin features:
  - View all appointments, customers, vehicles
  - Assign mechanic
  - Update status (`Pending -> In Progress -> Completed`)
  - On completion:
    - Add `service_history`
    - Auto-calculate `next_service_date` as `service_date + 90 days`
    - Generate bill in `bills`

## Project Structure

```text
.
├── app.py
├── aws_dynamo.py
├── config.py
├── requirements.txt
├── Procfile
├── runtime.txt
├── .env.example
├── templates/
└── static/
```

## DynamoDB Table Design

Create these tables in AWS DynamoDB:

### 1) users
- Partition key: `user_id` (String)
- Attributes: `name`, `email`, `phone`, `password`, `role`

### 2) vehicles
- Partition key: `vehicle_id` (String)
- Attributes: `user_id`, `vehicle_number`, `model`, `brand`, `year`
- Add GSI (recommended):
  - Index name: `user_id-index`
  - Partition key: `user_id`

### 3) appointments
- Partition key: `appointment_id` (String)
- Attributes: `user_id`, `vehicle_id`, `service_date`, `service_type`, `status`, `mechanic_id`

### 4) mechanics
- Partition key: `mechanic_id` (String)
- Attributes: `name`, `specialization`, `phone`

### 5) service_history
- Partition key: `history_id` (String)
- Attributes: `vehicle_id`, `service_date`, `details`, `cost`, `next_service_date`

### 6) bills
- Partition key: `bill_id` (String)
- Attributes: `appointment_id`, `amount`, `payment_status`

## Local Setup

1. Create virtual environment and install dependencies:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configure environment:

```bash
copy .env.example .env
```

Set values in `.env`:
- `SECRET_KEY`
- `AWS_REGION`
- `USE_IAM_ROLE=true` for EC2/Beanstalk IAM role (recommended)
- or `USE_IAM_ROLE=false` and set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

3. Run app:

```bash
python aws_table_setup.py
python app.py
```

Open: [http://localhost:5000](http://localhost:5000)
Default app URL in this project: [http://localhost:5055](http://localhost:5055)

## AWS Credential Setup

### Option A: IAM Role (Recommended)
- Attach IAM role to EC2/Elastic Beanstalk with DynamoDB permissions:
  - `dynamodb:GetItem`
  - `dynamodb:PutItem`
  - `dynamodb:UpdateItem`
  - `dynamodb:Query`
  - `dynamodb:Scan`

Set:
- `USE_IAM_ROLE=true`

### Option B: Access Key in Env
- Set:
  - `USE_IAM_ROLE=false`
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`

## Deployment (EC2)

1. Launch EC2 instance (Amazon Linux/Ubuntu), install Python 3.11+, pip.
2. Clone/upload project.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables (`.env` or system env).
5. Run with Gunicorn:

```bash
gunicorn app:app --bind 0.0.0.0:8000
```

6. Put Nginx in front of Gunicorn for production.

## Deployment (Elastic Beanstalk)

1. Ensure these files exist (already included):
   - `Procfile`
   - `runtime.txt`
2. Create Elastic Beanstalk Python environment.
3. Upload project bundle.
4. Configure environment variables in Elastic Beanstalk console.
5. Attach IAM role with DynamoDB access.
6. Deploy.

## Notes

- Default mechanics are auto-seeded on app startup if table is empty.
- For production scale, add additional GSIs and avoid scans where possible.
- Add CSRF protection and stricter input validation for enterprise-grade security.
