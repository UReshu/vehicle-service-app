import uuid
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from config import Config


def _to_iso_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value


def _to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


class DynamoService:
    def __init__(self):
        self._offline_path = Path(__file__).resolve().parent / "offline_store.json"
        self.offline_mode = False
        self._offline = {
            "users": {},
            "vehicles": {},
            "appointments": {},
            "mechanics": {},
            "service_history": {},
            "bills": {},
        }

        session_args = {"region_name": Config.AWS_REGION}
        if not Config.USE_IAM_ROLE and Config.AWS_ACCESS_KEY_ID and Config.AWS_SECRET_ACCESS_KEY:
            session_args.update(
                {
                    "aws_access_key_id": Config.AWS_ACCESS_KEY_ID,
                    "aws_secret_access_key": Config.AWS_SECRET_ACCESS_KEY,
                }
            )

        try:
            self.dynamo = boto3.resource("dynamodb", **session_args)
            self.users = self.dynamo.Table(Config.USERS_TABLE)
            self.vehicles = self.dynamo.Table(Config.VEHICLES_TABLE)
            self.appointments = self.dynamo.Table(Config.APPOINTMENTS_TABLE)
            self.mechanics = self.dynamo.Table(Config.MECHANICS_TABLE)
            self.service_history = self.dynamo.Table(Config.SERVICE_HISTORY_TABLE)
            self.bills = self.dynamo.Table(Config.BILLS_TABLE)
            # Verify connectivity at startup; fallback to offline mode if missing credentials or table access.
            self.mechanics.scan(Limit=1)
        except (NoCredentialsError, ClientError, BotoCoreError):
            self.offline_mode = True
            self._load_offline_store()

    def _load_offline_store(self):
        if not self._offline_path.exists():
            return
        try:
            data = json.loads(self._offline_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key in self._offline.keys():
                    value = data.get(key, {})
                    if isinstance(value, dict):
                        self._offline[key] = value
        except (json.JSONDecodeError, OSError):
            # Keep empty in-memory structure if file is invalid or unreadable.
            pass

    def _save_offline_store(self):
        try:
            self._offline_path.write_text(json.dumps(self._offline, indent=2), encoding="utf-8")
        except OSError:
            pass

    # ---------- Users ----------
    def create_user(self, name, email, phone, password_hash, role="customer"):
        user_id = str(uuid.uuid4())
        item = {
            "user_id": user_id,
            "name": name,
            "email": email,
            "phone": phone,
            "password": password_hash,
            "role": role,
        }
        if self.offline_mode:
            self._offline["users"][user_id] = item
            self._save_offline_store()
            return item
        self.users.put_item(Item=item)
        return item

    def get_user_by_email(self, email):
        if self.offline_mode:
            for user in self._offline["users"].values():
                if user.get("email") == email:
                    return user
            return None
        # Fallback scan for simplicity; prefer a GSI on email in production.
        result = self.users.scan(FilterExpression=Attr("email").eq(email))
        items = result.get("Items", [])
        return items[0] if items else None

    def get_all_users(self):
        if self.offline_mode:
            return list(self._offline["users"].values())
        result = self.users.scan()
        return result.get("Items", [])

    # ---------- Vehicles ----------
    def create_vehicle(self, user_id, vehicle_number, model, brand, year):
        vehicle_id = str(uuid.uuid4())
        item = {
            "vehicle_id": vehicle_id,
            "user_id": user_id,
            "vehicle_number": vehicle_number,
            "model": model,
            "brand": brand,
            "year": str(year),
        }
        if self.offline_mode:
            self._offline["vehicles"][vehicle_id] = item
            self._save_offline_store()
            return item
        self.vehicles.put_item(Item=item)
        return item

    def get_vehicles_by_user(self, user_id):
        if self.offline_mode:
            return [v for v in self._offline["vehicles"].values() if v.get("user_id") == user_id]
        # Requires user_id GSI named user_id-index for optimal query.
        try:
            result = self.vehicles.query(
                IndexName="user_id-index",
                KeyConditionExpression=Key("user_id").eq(user_id),
            )
            return result.get("Items", [])
        except Exception:
            result = self.vehicles.scan(FilterExpression=Attr("user_id").eq(user_id))
            return result.get("Items", [])

    def get_vehicle(self, vehicle_id):
        if self.offline_mode:
            return self._offline["vehicles"].get(vehicle_id)
        result = self.vehicles.get_item(Key={"vehicle_id": vehicle_id})
        return result.get("Item")

    def get_all_vehicles(self):
        if self.offline_mode:
            return list(self._offline["vehicles"].values())
        return self.vehicles.scan().get("Items", [])

    # ---------- Appointments ----------
    def create_appointment(self, user_id, vehicle_id, service_date, service_type):
        appointment_id = str(uuid.uuid4())
        item = {
            "appointment_id": appointment_id,
            "user_id": user_id,
            "vehicle_id": vehicle_id,
            "service_date": _to_iso_date(service_date),
            "service_type": service_type,
            "status": "Pending",
            "mechanic_id": "",
        }
        if self.offline_mode:
            self._offline["appointments"][appointment_id] = item
            self._save_offline_store()
            return item
        self.appointments.put_item(Item=item)
        return item

    def get_appointments_by_user(self, user_id):
        if self.offline_mode:
            return [a for a in self._offline["appointments"].values() if a.get("user_id") == user_id]
        result = self.appointments.scan(FilterExpression=Attr("user_id").eq(user_id))
        return result.get("Items", [])

    def get_all_appointments(self):
        if self.offline_mode:
            return list(self._offline["appointments"].values())
        return self.appointments.scan().get("Items", [])

    def get_appointment(self, appointment_id):
        if self.offline_mode:
            return self._offline["appointments"].get(appointment_id)
        result = self.appointments.get_item(Key={"appointment_id": appointment_id})
        return result.get("Item")

    def update_appointment_status(self, appointment_id, status, mechanic_id=""):
        if self.offline_mode:
            appt = self._offline["appointments"].get(appointment_id)
            if appt:
                appt["status"] = status
                appt["mechanic_id"] = mechanic_id
                self._save_offline_store()
            return
        update_expr = "SET #status = :status, mechanic_id = :mechanic_id"
        values = {":status": status, ":mechanic_id": mechanic_id}
        names = {"#status": "status"}
        self.appointments.update_item(
            Key={"appointment_id": appointment_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=values,
            ExpressionAttributeNames=names,
        )

    # ---------- Mechanics ----------
    def get_all_mechanics(self):
        if self.offline_mode:
            return list(self._offline["mechanics"].values())
        return self.mechanics.scan().get("Items", [])

    def seed_default_mechanics(self):
        mechanics = self.get_all_mechanics()
        if mechanics:
            return
        defaults = [
            {"mechanic_id": str(uuid.uuid4()), "name": "Amit Kumar", "specialization": "Engine", "phone": "9000000001"},
            {"mechanic_id": str(uuid.uuid4()), "name": "Ravi Singh", "specialization": "Electrical", "phone": "9000000002"},
            {"mechanic_id": str(uuid.uuid4()), "name": "Neha Patel", "specialization": "General Service", "phone": "9000000003"},
        ]
        if self.offline_mode:
            for mechanic in defaults:
                self._offline["mechanics"][mechanic["mechanic_id"]] = mechanic
            self._save_offline_store()
            return
        for mechanic in defaults:
            self.mechanics.put_item(Item=mechanic)

    # ---------- Service History ----------
    def add_service_history(self, vehicle_id, service_date, details, cost):
        history_id = str(uuid.uuid4())
        service_date_obj = datetime.strptime(_to_iso_date(service_date), "%Y-%m-%d")
        next_service_date = (service_date_obj + timedelta(days=90)).date().isoformat()
        item = {
            "history_id": history_id,
            "vehicle_id": vehicle_id,
            "service_date": service_date_obj.date().isoformat(),
            "details": details,
            "cost": Decimal(str(cost)),
            "next_service_date": next_service_date,
        }
        if self.offline_mode:
            item["cost"] = float(item["cost"])
            self._offline["service_history"][history_id] = item
            self._save_offline_store()
            return item
        self.service_history.put_item(Item=item)
        return item

    def get_history_by_vehicle(self, vehicle_id):
        if self.offline_mode:
            items = [h for h in self._offline["service_history"].values() if h.get("vehicle_id") == vehicle_id]
            items.sort(key=lambda x: x.get("service_date", ""), reverse=True)
            return items
        result = self.service_history.scan(FilterExpression=Attr("vehicle_id").eq(vehicle_id))
        items = result.get("Items", [])
        for item in items:
            item["cost"] = _to_float(item.get("cost"))
        items.sort(key=lambda x: x.get("service_date", ""), reverse=True)
        return items

    def get_latest_history_for_vehicle(self, vehicle_id):
        history = self.get_history_by_vehicle(vehicle_id)
        return history[0] if history else None

    # ---------- Billing ----------
    def create_bill(self, appointment_id, amount, payment_status="Pending"):
        bill_id = str(uuid.uuid4())
        item = {
            "bill_id": bill_id,
            "appointment_id": appointment_id,
            "amount": Decimal(str(amount)),
            "payment_status": payment_status,
        }
        if self.offline_mode:
            item["amount"] = float(item["amount"])
            self._offline["bills"][bill_id] = item
            self._save_offline_store()
            return item
        self.bills.put_item(Item=item)
        item["amount"] = float(item["amount"])
        return item

    def get_bill_by_appointment(self, appointment_id):
        if self.offline_mode:
            for bill in self._offline["bills"].values():
                if bill.get("appointment_id") == appointment_id:
                    return bill
            return None
        result = self.bills.scan(FilterExpression=Attr("appointment_id").eq(appointment_id))
        items = result.get("Items", [])
        if not items:
            return None
        bill = items[0]
        bill["amount"] = _to_float(bill.get("amount"))
        return bill
