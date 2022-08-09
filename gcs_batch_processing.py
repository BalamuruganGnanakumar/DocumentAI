# type: ignore[1]
"""
Makes a Batch Processing Request to Document AI
Creates request with full directory in Cloud Storage
"""
import re
import argparse
from typing import List

from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai
from google.cloud import storage


parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('-p','--project', metavar='N',required=True,
                    help='Project Id')
parser.add_argument('-l','--location', metavar='N',  default='us',
                    help='Location')

parser.add_argument('-d','--processor' ,metavar='N',  required=True,
                    help='processor ID')

parser.add_argument('-i','----igcs', metavar='N',  required=True,
                    help='processor ID')

parser.add_argument('-o','--ogcs', metavar='N',  required=True,
                    help='processor ID')

args = parser.parse_args()


#PROJECT_ID = "r1-epic"
PROJECT_ID = args.project
#LOCATION = "us"  # Format is 'us' or 'eu'
LOCATION = args.location # Format is 'us' or 'eu'
#PROCESSOR_ID = "c5b6a28f546e35d3"  # Create processor in Cloud Console
PROCESSOR_ID = args.processor

# Format 'gs://input_bucket/directory'
#GCS_INPUT_PREFIX = "gs://woodruff_input_july_22/QuoteProcessing/StarStone"
GCS_INPUT_PREFIX = args.igcs

# Format 'gs://output_bucket/directory'
#GCS_OUTPUT_URI = "gs://woodruff_input_july_22/QuoteProcessing/StarStone/parsed"
GCS_OUTPUT_URI = args.ogcs

# Instantiates a client
docai_client = documentai.DocumentProcessorServiceClient(
    client_options=ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
)

# The full resource name of the processor, e.g.:
# projects/project-id/locations/location/processor/processor-id
# You must create new processors in the Cloud Console first
RESOURCE_NAME = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

# Cloud Storage URI for the Input Directory
gcs_prefix = documentai.GcsPrefix(gcs_uri_prefix=GCS_INPUT_PREFIX)

# Load GCS Input URI into Batch Input Config
input_config = documentai.BatchDocumentsInputConfig(gcs_prefix=gcs_prefix)

# Cloud Storage URI for Output directory
gcs_output_config = documentai.DocumentOutputConfig.GcsOutputConfig(
    gcs_uri=GCS_OUTPUT_URI
)

# Load GCS Output URI into OutputConfig object
output_config = documentai.DocumentOutputConfig(gcs_output_config=gcs_output_config)

# Configure Process Request
request = documentai.BatchProcessRequest(
    name=RESOURCE_NAME,
    input_documents=input_config,
    document_output_config=output_config,
)

# Batch Process returns a Long Running Operation (LRO)
operation = docai_client.batch_process_documents(request)

# Continually polls the operation until it is complete.
# This could take some time for larger files
# Format: projects/PROJECT_NUMBER/locations/LOCATION/operations/OPERATION_ID
print(f"Waiting for operation {operation.operation.name} to complete...")
operation.result()

# NOTE: Can also use callbacks for asynchronous processing
#
# def my_callback(future):
#   result = future.result()
#
# operation.add_done_callback(my_callback)

print("Document processing complete.")

# Once the operation is complete,
# get output document information from operation metadata
metadata = documentai.BatchProcessMetadata(operation.metadata)

if metadata.state != documentai.BatchProcessMetadata.State.SUCCEEDED:
    raise ValueError(f"Batch Process Failed: {metadata.state_message}")

documents: List[documentai.Document] = []

# Storage Client to retrieve the output files from GCS
storage_client = storage.Client()

# One process per Input Document
# pylint: disable=not-an-iterable
for process in metadata.individual_process_statuses:

    # output_gcs_destination format: gs://BUCKET/PREFIX/OPERATION_NUMBER/0
    # The GCS API requires the bucket name and URI prefix separately
    output_bucket, output_prefix = re.match(
        r"gs://(.*?)/(.*)", process.output_gcs_destination
    ).groups()

    # Get List of Document Objects from the Output Bucket
    output_blobs = storage_client.list_blobs(output_bucket, prefix=output_prefix)

    # DocAI may output multiple JSON files per source file
    for blob in output_blobs:
        # Document AI should only output JSON files to GCS
        if ".json" not in blob.name:
            print(f"Skipping non-supported file type {blob.name}")
            continue

        print(f"Fetching {blob.name}")

        # Download JSON File and Convert to Document Object
        document = documentai.Document.from_json(
            blob.download_as_bytes(), ignore_unknown_fields=True
        )

        documents.append(document)

# Print Text from all documents
# Truncated at 100 characters for brevity
for document in documents:
    print(document.text[:100])
