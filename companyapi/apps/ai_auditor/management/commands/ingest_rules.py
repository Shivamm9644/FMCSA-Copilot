from django.core.management.base import BaseCommand
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from google import genai
from google.genai import types

class Command(BaseCommand):
    help = 'Ingests FMCSA rules into Qdrant for production RAG'

    def handle(self, *args, **kwargs):
        self.stdout.write("Initializing Qdrant client...")
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "qdrant_data")
        os.makedirs(db_path, exist_ok=True)
        
        try:
            client = QdrantClient(path=db_path)
            collection_name = "fmcsa_rules"
            
            # Check if collection exists
            if not client.collection_exists(collection_name):
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                )
                self.stdout.write(self.style.SUCCESS(f"Created collection {collection_name}"))
            
            # Create synthetic FMCSA rules for Phase 12 if no file provided
            # (as discussed in open questions, since no specific PDF was provided)
            rules = [
                {"text": "§ 395.15(a): Automatic on-board recording devices must be synchronized with the operations of the engine.", "category": "engine_sync"},
                {"text": "§ 395.22(h): A motor carrier must ensure that its ELDs are calibrated to track miles and hours within 1% accuracy.", "category": "calibration"},
                {"text": "§ 395.34(a): A driver must provide written notice to the motor carrier within 24 hours of an ELD malfunction.", "category": "malfunction"},
                {"text": "Diagnostic events must be logged if data is missing or power drops for more than 1 minute.", "category": "diagnostic"},
                {"text": "HOS limits: 11 hours driving, 14 hours on-duty, 30-minute break required after 8 hours.", "category": "hos"},
            ]
            
            google_api_key = os.environ.get("GOOGLE_API_KEY", "")
            if not google_api_key:
                self.stdout.write(self.style.ERROR("GOOGLE_API_KEY not found. Skipping embedding generation."))
                return

            genai_client = genai.Client(api_key=google_api_key)
            
            points = []
            for i, rule in enumerate(rules):
                self.stdout.write(f"Embedding rule {i+1}/{len(rules)}...")
                result = genai_client.models.embed_content(
                    model="text-embedding-004",
                    contents=rule["text"],
                )
                
                points.append(PointStruct(
                    id=i,
                    vector=result.embeddings[0].values,
                    payload={"text": rule["text"], "category": rule["category"]}
                ))
                
            client.upsert(
                collection_name=collection_name,
                wait=True,
                points=points
            )
            
            self.stdout.write(self.style.SUCCESS("Successfully ingested synthetic FMCSA rules into Qdrant!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to ingest: {e}"))
