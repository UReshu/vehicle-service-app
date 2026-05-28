import boto3
from botocore.exceptions import ClientError

from config import Config


def get_client():
    kwargs = {"region_name": Config.AWS_REGION}
    if not Config.USE_IAM_ROLE and Config.AWS_ACCESS_KEY_ID and Config.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = Config.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = Config.AWS_SECRET_ACCESS_KEY
    return boto3.client("dynamodb", **kwargs)


def create_table_if_missing(client, table_name, key_schema, attribute_definitions, gsi=None):
    try:
        client.describe_table(TableName=table_name)
        print(f"Table exists: {table_name}")
        return
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    params = {
        "TableName": table_name,
        "KeySchema": key_schema,
        "AttributeDefinitions": attribute_definitions,
        "BillingMode": "PAY_PER_REQUEST",
    }
    if gsi:
        params["GlobalSecondaryIndexes"] = gsi
    client.create_table(**params)
    print(f"Creating table: {table_name}")


def main():
    client = get_client()

    create_table_if_missing(
        client,
        Config.USERS_TABLE,
        key_schema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        attribute_definitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
    )

    create_table_if_missing(
        client,
        Config.VEHICLES_TABLE,
        key_schema=[{"AttributeName": "vehicle_id", "KeyType": "HASH"}],
        attribute_definitions=[
            {"AttributeName": "vehicle_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        gsi=[
            {
                "IndexName": "user_id-index",
                "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )

    create_table_if_missing(
        client,
        Config.APPOINTMENTS_TABLE,
        key_schema=[{"AttributeName": "appointment_id", "KeyType": "HASH"}],
        attribute_definitions=[{"AttributeName": "appointment_id", "AttributeType": "S"}],
    )

    create_table_if_missing(
        client,
        Config.MECHANICS_TABLE,
        key_schema=[{"AttributeName": "mechanic_id", "KeyType": "HASH"}],
        attribute_definitions=[{"AttributeName": "mechanic_id", "AttributeType": "S"}],
    )

    create_table_if_missing(
        client,
        Config.SERVICE_HISTORY_TABLE,
        key_schema=[{"AttributeName": "history_id", "KeyType": "HASH"}],
        attribute_definitions=[{"AttributeName": "history_id", "AttributeType": "S"}],
    )

    create_table_if_missing(
        client,
        Config.BILLS_TABLE,
        key_schema=[{"AttributeName": "bill_id", "KeyType": "HASH"}],
        attribute_definitions=[{"AttributeName": "bill_id", "AttributeType": "S"}],
    )

    print("All required tables are ready.")


if __name__ == "__main__":
    main()
