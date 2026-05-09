import firebase_admin
from firebase_admin import credentials, firestore

# 1. SETUP: Initialize the connection
# This block ensures we only connect once to avoid errors
if not firebase_admin._apps:
    # Ensure 'firebase_key.json' is in the same folder as this script
    cred = credentials.Certificate("source/service_key.json")
    firebase_admin.initialize_app(cred)

# 2. CREATE CLIENT: The tool used to talk to your database
db = firestore.client()

# 3. THE SYNC FUNCTION: This is what your GUI will use
def sync_to_cloud(collection_name, document_id, data_dict):
    """
    Sends data to Firestore.
    :param collection_name: Name of the 'table' in Firebase (e.g., 'orders')
    :param document_id: The unique ID (e.g., your PostgreSQL Order ID)
    :param data_dict: A Python dictionary of the data to save
    """
    try:
        # Reference the collection and document, then save the data
        doc_ref = db.collection(collection_name).document(str(document_id))
        
        # We use .set() to create or completely overwrite the document
        doc_ref.set(data_dict)
        
        print(f"✔️ Successfully synced Document {document_id} to {collection_name}")
        return True
    except Exception as e:
        print(f"❌ Cloud Sync Error: {e}")
        return False

# 4. OPTIONAL: A function to update just one field (like Order Status)
def update_cloud_status(collection_name, document_id, new_status):
    try:
        doc_ref = db.collection(collection_name).document(str(document_id))
        doc_ref.update({"status": new_status})
        return True
    except Exception as e:
        print(f"❌ Update Error: {e}")
        return False