import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain_google_genai import GoogleGenerativeAIEmbeddings

class QdrantService:
    _client = None
    COLLECTION_NAME = "fmcsa_rules_real"

    @classmethod
    def get_client(cls):
        if cls._client is None:
            # Use in-memory to prevent file-lock crashes between Django and Celery processes
            cls._client = QdrantClient(location=":memory:")
            cls._seed_real_data(cls._client)
        return cls._client

    @classmethod
    def _seed_real_data(cls, client):
        if client.collection_exists(cls.COLLECTION_NAME):
            return
            
        fmcsa_docs = [
            {
                "text": "The motor carrier must ensure that its ELDs are calibrated to track miles and hours within 1% accuracy. The odometer value must be synchronized with the CMV's engine.",
                "regulation": "49 CFR Part 395 Appendix A - § 4.3.1.2",
                "source": "ELD Technical Specifications"
            },
            {
                "text": "A driver must provide written notice to the motor carrier within 24 hours of an ELD malfunction. The carrier must repair or replace it within 8 days.",
                "regulation": "49 CFR § 395.34(a)",
                "source": "ELD Malfunction Procedures"
            },
            {
                "text": "Diagnostic events (e.g., Power Data Diagnostic, Engine Synchronization Data Diagnostic) must be logged if data is missing, if there are positioning compliance anomalies, or if power drops for more than 1 minute while the vehicle is in motion.",
                "regulation": "49 CFR Part 395 Appendix A - § 4.6.1",
                "source": "Diagnostic Event Codes"
            },
            {
                "text": "Property-carrying drivers may drive a maximum of 11 hours after 10 consecutive hours off duty. May not drive beyond the 14th consecutive hour after coming on duty.",
                "regulation": "49 CFR § 395.3(a)",
                "source": "Hours of Service Rules"
            },
            {
                "text": "A driver must take a 30-minute break when they have driven for a period of 8 cumulative hours without at least a 30-minute interruption.",
                "regulation": "49 CFR § 395.3(a)(3)(ii)",
                "source": "Hours of Service Rules"
            },
            {
                "text": "To be compliant, the ELD must continuously record the CMV's latitude and longitude coordinates, accurate to within 1 mile during driving.",
                "regulation": "49 CFR Part 395 Appendix A - § 4.3.1.6",
                "source": "ELD Technical Specifications"
            }
        ]
        
        docs = [d['text'] for d in fmcsa_docs]
        metadata = [{"regulation": d['regulation'], "source": d['source']} for d in fmcsa_docs]
        
        client.add(
            collection_name=cls.COLLECTION_NAME,
            documents=docs,
            metadata=metadata
        )

    @classmethod
    def retrieve_context(cls, query: str, limit: int = 2, category: str = None) -> list:
        client = cls.get_client()
        
        try:
            # Check if collection exists
            if not client.collection_exists(cls.COLLECTION_NAME):
                return []

            search_result = client.query(
                collection_name=cls.COLLECTION_NAME,
                query_text=query,
                limit=limit
            )
            
            # Return list of dictionaries containing text, regulation, source
            return [
                {
                    "text": hit.document or hit.metadata.get("document", ""),
                    "regulation": hit.metadata.get("regulation", ""),
                    "source": hit.metadata.get("source", ""),
                    "score": hit.score
                }
                for hit in search_result
            ]
        except Exception as e:
            print(f"Qdrant query failed: {e}")
            return []

    # Hardcoded docs for keyword fallback (mirrors _seed_real_data)
    _FMCSA_DOCS = [
        {"text": "The motor carrier must ensure that its ELDs are calibrated to track miles and hours within 1% accuracy. The odometer value must be synchronized with the CMV's engine.", "regulation": "49 CFR Part 395 Appendix A - § 4.3.1.2", "source": "ELD Technical Specifications"},
        {"text": "A driver must provide written notice to the motor carrier within 24 hours of an ELD malfunction. The carrier must repair or replace it within 8 days.", "regulation": "49 CFR § 395.34(a)", "source": "ELD Malfunction Procedures"},
        {"text": "Diagnostic events (e.g., Power Data Diagnostic, Engine Synchronization Data Diagnostic) must be logged if data is missing, if there are positioning compliance anomalies, or if power drops for more than 1 minute while the vehicle is in motion.", "regulation": "49 CFR Part 395 Appendix A - § 4.6.1", "source": "Diagnostic Event Codes"},
        {"text": "Property-carrying drivers may drive a maximum of 11 hours after 10 consecutive hours off duty. May not drive beyond the 14th consecutive hour after coming on duty.", "regulation": "49 CFR § 395.3(a)", "source": "Hours of Service Rules"},
        {"text": "A driver must take a 30-minute break when they have driven for a period of 8 cumulative hours without at least a 30-minute interruption.", "regulation": "49 CFR § 395.3(a)(3)(ii)", "source": "Hours of Service Rules"},
        {"text": "To be compliant, the ELD must continuously record the CMV's latitude and longitude coordinates, accurate to within 1 mile during driving.", "regulation": "49 CFR Part 395 Appendix A - § 4.3.1.6", "source": "ELD Technical Specifications"},
    ]

    @classmethod
    def keyword_fallback(cls, query: str) -> list:
        """Simple keyword search over seeded FMCSA docs as a fallback."""
        query_lower = query.lower()
        keywords = [w for w in query_lower.split() if len(w) > 3]
        if not keywords:
            return []
            
        scored = []
        for doc in cls._FMCSA_DOCS:
            score = sum(1 for kw in keywords if kw in doc["text"].lower())
            if score > 0:
                scored.append({"text": doc["text"], "regulation": doc["regulation"], "source": doc["source"], "score": round(score / max(len(keywords), 1), 2)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:2]

