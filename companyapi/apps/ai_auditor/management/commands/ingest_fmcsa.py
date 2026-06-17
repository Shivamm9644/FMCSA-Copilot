import os
from django.core.management.base import BaseCommand
from langchain.text_splitter import RecursiveCharacterTextSplitter
from apps.ai_auditor.qdrant_service import QdrantService
from qdrant_client.models import PointStruct

class Command(BaseCommand):
    help = 'Ingest FMCSA document into Qdrant vector database.'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, nargs='?', help='Path to FMCSA text document')

    def handle(self, *args, **options):
        file_path = options.get('file_path')
        
        # If no file provided, create a mock one for demonstration
        if not file_path or not os.path.exists(file_path):
            self.stdout.write(self.style.WARNING(f"File not found or not provided. Using default mock rules."))
            text = """
FMCSA 395.15(c): ELD must detect missing location data.
FMCSA 395.11: Timing malfunctions occur when the device cannot synchronize with UTC time.
FMCSA 395.8: A driver must ensure their logs are certified.
FMCSA 395.22: A carrier must retain records for 6 months.
FMCSA 395.34: In the event of a malfunction, the driver must provide written notice to the carrier within 24 hours.
"""
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_text(text)
        
        self.stdout.write(f"Generated {len(chunks)} chunks.")
        
        # Initialize Qdrant Service
        qdrant = QdrantService()
        
        # Add metadata based on keywords
        if not os.environ.get("GOOGLE_API_KEY"):
            self.stdout.write(self.style.ERROR("GOOGLE_API_KEY is not set. Cannot generate embeddings."))
            return

        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        
        points = []
        for i, chunk in enumerate(chunks):
            vector = embeddings.embed_query(chunk)
            # Create meaningful metadata for filtering
            rule_type = "general"
            if "malfunction" in chunk.lower() or "diagnostic" in chunk.lower():
                rule_type = "hardware"
            elif "hour" in chunk.lower() or "duty" in chunk.lower():
                rule_type = "hos"
                
            points.append(
                PointStruct(id=i+1000, vector=vector, payload={
                    "text": chunk,
                    "source": file_path or "mock",
                    "rule_type": rule_type
                })
            )
            
        qdrant.get_client().upsert(
            collection_name=qdrant.COLLECTION_NAME,
            points=points
        )
        
        self.stdout.write(self.style.SUCCESS('Successfully ingested FMCSA document into Qdrant'))
