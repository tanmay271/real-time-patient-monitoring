"""Skeleton handler for the ingestion Lambda."""

import json
import os


def table_names():
    """Return the DynamoDB table names configured for ingestion."""
    return {
        "patients": os.environ["PATIENTS_TABLE"],
        "readings": os.environ["READINGS_TABLE"],
    }


def lambda_handler(event, context):
    """Return the not-yet-implemented ingestion response.

    Later ingestion tasks read the table names through ``table_names()``.
    """

    return {
        "statusCode": 500,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "ingestion is not implemented yet",
                }
            }
        ),
    }
