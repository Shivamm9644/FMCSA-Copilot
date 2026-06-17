import os
from django.core.management.base import BaseCommand
from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from google import genai

class Command(BaseCommand):
    help = 'Ingests a custom FMCSA rulebook PDF into Qdrant for production RAG'

    def add_arguments(self, parser):
        parser.add_argument('pdf_path', type=str, help='Path to the FMCSA rulebook PDF file')

    def handle(self, *args, **kwargs):
        pdf_path = kwargs['pdf_path']
        
        if not os.path.exists(pdf_path):
            self.stdout.write(self.style.ERROR(f"PDF file not found at: {pdf_path}"))
            return

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key or api_key == "your_gemini_api_key_here":
            self.stdout.write(self.style.ERROR("A valid GEMINI_API_KEY is required to generate embeddings. Please update your .env file."))
            return

        self.stdout.write(f"Reading PDF: {pdf_path}...")
        try:
            reader = PdfReader(pdf_path)
            full_text = ""
            for i, page in enumerate(reader.pages):
                full_text += page.extract_text() + "\n"
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to read PDF: {e}"))
            return

        self.stdout.write("Splitting text into chunks...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        chunks = text_splitter.split_text(full_text)
        self.stdout.write(f"Created {len(chunks)} text chunks.")

        self.stdout.write("Initializing Qdrant client...")
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "qdrant_data")
        os.makedirs(db_path, exist_ok=True)
        
        try:
            client = QdrantClient(path=db_path)
            collection_name = "fmcsa_rules"
            
            # Recreate collection to wipe old synthetic rules
            if client.collection_exists(collection_name):
                client.delete_collection(collection_name)
                self.stdout.write(self.style.WARNING(f"Deleted old '{collection_name}' collection."))

            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )
            self.stdout.write(self.style.SUCCESS(f"Created new collection '{collection_name}'"))
            
            genai_client = genai.Client(api_key=api_key)
            
            points = []
            for i, chunk in enumerate(chunks):
                self.stdout.write(f"Embedding chunk {i+1}/{len(chunks)}...")
                result = genai_client.models.embed_content(
                    model="text-embedding-004",
                    contents=chunk,
                )
                
                points.append(PointStruct(
                    id=i,
                    vector=result.embeddings[0].values,
                    payload={"text": chunk, "source": os.path.basename(pdf_path), "chunk_id": i}
                ))
                
            client.upsert(
                collection_name=collection_name,
                wait=True,
                points=points
            )
            
            self.stdout.write(self.style.SUCCESS(f"Successfully ingested {len(chunks)} chunks into Qdrant!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to ingest to Qdrant: {e}"))
