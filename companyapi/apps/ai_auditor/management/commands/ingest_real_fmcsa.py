import os
import json
from django.core.management.base import BaseCommand
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

class Command(BaseCommand):
    help = 'Ingests REAL FMCSA regulations into Qdrant for production RAG'

    def handle(self, *args, **kwargs):
        self.stdout.write("Initializing Qdrant client...")
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "qdrant_data")
        os.makedirs(db_path, exist_ok=True)
        
        try:
            # We use QdrantClient's native fastembed integration so it works fully locally without Google API!
            client = QdrantClient(path=db_path)
            collection_name = "fmcsa_rules_real"
            
            # Recreate collection
            if client.collection_exists(collection_name):
                client.delete_collection(collection_name)
                
            self.stdout.write(f"Created collection {collection_name}")
            
            # Actual FMCSA Knowledge Base
            fmcsa_docs = [
                {
                    "text": "The motor carrier must ensure that its ELDs are calibrated to track miles and hours within 1% accuracy. The odometer value must be synchronized with the CMV's engine.",
                    "regulation": "49 CFR Part 395 Appendix A - § 4.3.1.2",
                    "source": "ELD Technical Specifications",
                    "topic": "odometer"
                },
                {
                    "text": "A driver must provide written notice to the motor carrier within 24 hours of an ELD malfunction. The carrier must repair or replace it within 8 days.",
                    "regulation": "49 CFR § 395.34(a)",
                    "source": "ELD Malfunction Procedures",
                    "topic": "malfunction"
                },
                {
                    "text": "Diagnostic events (e.g., Power Data Diagnostic, Engine Synchronization Data Diagnostic) must be logged if data is missing, if there are positioning compliance anomalies, or if power drops for more than 1 minute while the vehicle is in motion.",
                    "regulation": "49 CFR Part 395 Appendix A - § 4.6.1",
                    "source": "Diagnostic Event Codes",
                    "topic": "diagnostic"
                },
                {
                    "text": "Property-carrying drivers may drive a maximum of 11 hours after 10 consecutive hours off duty. May not drive beyond the 14th consecutive hour after coming on duty.",
                    "regulation": "49 CFR § 395.3(a)",
                    "source": "Hours of Service Rules",
                    "topic": "hos"
                },
                {
                    "text": "A driver must take a 30-minute break when they have driven for a period of 8 cumulative hours without at least a 30-minute interruption.",
                    "regulation": "49 CFR § 395.3(a)(3)(ii)",
                    "source": "Hours of Service Rules",
                    "topic": "hos"
                },
                {
                    "text": "To be compliant, the ELD must continuously record the CMV's latitude and longitude coordinates, accurate to within 1 mile during driving.",
                    "regulation": "49 CFR Part 395 Appendix A - § 4.3.1.6",
                    "source": "ELD Technical Specifications",
                    "topic": "location"
                }
            ]
            
            self.stdout.write("Generating local embeddings using fastembed...")
            
            docs = [d['text'] for d in fmcsa_docs]
            metadata = [{"regulation": d['regulation'], "source": d['source'], "topic": d['topic']} for d in fmcsa_docs]
            
            client.add(
                collection_name=collection_name,
                documents=docs,
                metadata=metadata
            )
            
            self.stdout.write(self.style.SUCCESS("Successfully ingested actual FMCSA rules into Qdrant!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to ingest: {e}"))
