# Project A: Order ->Payment -> Notify API Demo

This is a simple Django-based API for handling **orders** and **mobile money (MoMo) payments**, including idempotent charges and webhook callbacks.

---

## Technology Stack

- **Django, Django Rest Framework, & Python**: Core web framework for API endpoints and business logic  
- **Celery**: Distributed task queue to handle background tasks (sending messages)  
- **Redis**: Message broker for Celery, enabling communication between web and worker services  
- **PostgreSQL**: Primary database for storage 
- **Docker & Docker Compose**: Orchestration for all services, providing a consistent isolated environment

## Features


- Order Management: Create and retrieve orders via a REST API.

- Payment Processing: Initiate a payment for a specific order. Uses an Idempotency-Key to prevent duplicate requests.

- Secure Webhook Handling: Validates requests using an HMAC signature to ensure authenticity.

- Idempotent: Safe against replayed webhook events.

- Background Task Integration: Mock background job enqueued after successful payment.

---

## API Endpoints

### 1. Create Order
**POST** `/api/orders/`

**Request**
```http
POST /api/orders/
Host: 127.0.0.1:8000
Content-Type: application/json

{
  "customer": <customer_id>,
  "items": [
    {"product": "<product_uuid>", "quantity": <qty>}
  ]
}
```

### 2. Get Order by ID
**GET** `/api/orders/<order_uuid>/`

**Request**

```http
GET /api/orders/<order_uuid>/
Host: 127.0.0.1:8000

```
### 3. Charge Order
**POST** `/api/payments/charge/`
 
**Request**

```http
POST /api/payments/charge/
Host: 127.0.0.1:8000
Content-Type: application/json
Idempotency-Key: <idem_key>

{
  "order": "<order_uuid>"
}
```

### 4. MoMo Webhook
**POST** `/api/webhooks/momo/`

**Request**

```http
POST /api/webhooks/momo/
Host: 127.0.0.1:8000
Content-Type: application/json
X-Momo-Signature: <hmac_signature>

{
  "provider_reference": "<momo_txn_id>",
  "order_id": "<order_uuid>",
  "status": "success"
}
```

## Running with Docker
1. Build the Docker image 
```
docker-compose build
```

2. Run the container 
```
docker-compose up
```

**The API will be available at:**
 `http://127.0.0.1:8000`

## Running Tests
**Run tests inside the container:**

 ```
 docker compose run --rm web pytest
 ```

## Environment Variables

**Make sure to configure any environment variables in your .env file (if required):**
```
MOMO_WEBHOOK_SECRET=<MOMO_WEBHOOK_SECRET>
POSTGRES_DB=<db_name>
POSTGRES_USER=<db_user>
POSTGRES_PASSWORD=<db_password>
POSTGRES_HOST=<db_host>
POSTGRES_PORT=<db_port>
```

How to Use:

- Install the REST Client extension in VS Code.

- Open the api.http or api.rest file in the base directory.

- Hover over a request and click "Send Request".









