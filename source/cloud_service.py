import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    cred = credentials.Certificate(
        r"D:\GIKI\4th Semester\Projects\RestroCore\source\service_key.json"
    )
    firebase_admin.initialize_app(cred)

    db = firestore.client()

def sync_to_cloud(collection_name, document_id, data_dict):
    try:
        doc_ref = db.collection(collection_name).document(str(document_id))
        doc_ref.set(data_dict, merge=True)
        print(f"✔️ Successfully synced Document {document_id} to {collection_name}")
        return True
    except Exception as e:
        print(f"❌ Cloud Sync Error: {e}")
        return False

def update_cloud_field(collection_name, document_id, field_name, new_value):
    try:
        doc_ref = db.collection(collection_name).document(str(document_id))
        doc_ref.set({field_name: new_value}, merge=True)
        print(f"✔️ Updated {field_name} = '{new_value}' on Document {document_id}")
        return True
    except Exception as e:
        print(f"❌ Update Error: {e}")
        return False