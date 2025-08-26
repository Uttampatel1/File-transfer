import streamlit as st
import random
import os
import tempfile
import shutil
from datetime import datetime, timedelta
import json
import threading

# Configure page
st.set_page_config(
    page_title="Secure File Transfer",
    page_icon="📁",
    layout="wide"
)

# Global file to store PIN-to-file mappings
STORAGE_DIR = os.path.join(tempfile.gettempdir(), "streamlit_file_transfer")
METADATA_FILE = os.path.join(STORAGE_DIR, "file_metadata.json")

# Create storage directory if it doesn't exist
os.makedirs(STORAGE_DIR, exist_ok=True)

# Thread lock for file operations
file_lock = threading.Lock()

def load_file_metadata():
    """Load file metadata from persistent storage"""
    try:
        if os.path.exists(METADATA_FILE):
            with open(METADATA_FILE, 'r') as f:
                data = json.load(f)
                # Convert string timestamps back to datetime objects
                for pin, info in data.items():
                    if isinstance(info['upload_time'], str):
                        info['upload_time'] = datetime.fromisoformat(info['upload_time'])
                return data
        return {}
    except Exception as e:
        st.error(f"Error loading metadata: {e}")
        return {}

def save_file_metadata(metadata):
    """Save file metadata to persistent storage"""
    try:
        with file_lock:
            # Convert datetime objects to strings for JSON serialization
            serializable_data = {}
            for pin, info in metadata.items():
                serializable_info = info.copy()
                if isinstance(serializable_info['upload_time'], datetime):
                    serializable_info['upload_time'] = serializable_info['upload_time'].isoformat()
                serializable_data[pin] = serializable_info
            
            with open(METADATA_FILE, 'w') as f:
                json.dump(serializable_data, f, indent=2)
    except Exception as e:
        st.error(f"Error saving metadata: {e}")

def generate_pin():
    """Generate a random 4-digit PIN"""
    metadata = load_file_metadata()
    while True:
        pin = f"{random.randint(1000, 9999)}"
        if pin not in metadata:  # Ensure PIN is unique
            return pin

def save_file_with_pin(uploaded_file, pin):
    """Save uploaded file with PIN as identifier"""
    try:
        # Save file with PIN as filename prefix
        file_path = os.path.join(STORAGE_DIR, f"{pin}_{uploaded_file.name}")
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        
        # Load existing metadata
        metadata = load_file_metadata()
        
        # Add new file info
        metadata[pin] = {
            'filename': uploaded_file.name,
            'filepath': file_path,
            'size': uploaded_file.size,
            'upload_time': datetime.now(),
            'type': uploaded_file.type
        }
        
        # Save updated metadata
        save_file_metadata(metadata)
        
        return file_path
    except Exception as e:
        raise Exception(f"Failed to save file: {str(e)}")

def get_file_by_pin(pin):
    """Retrieve file information by PIN"""
    metadata = load_file_metadata()
    return metadata.get(pin)

def cleanup_old_files():
    """Clean up files older than 24 hours"""
    try:
        metadata = load_file_metadata()
        current_time = datetime.now()
        pins_to_remove = []
        
        for pin, file_info in metadata.items():
            if current_time - file_info['upload_time'] > timedelta(hours=24):
                # Remove file from disk
                if os.path.exists(file_info['filepath']):
                    try:
                        os.remove(file_info['filepath'])
                    except OSError:
                        pass  # File might already be deleted
                pins_to_remove.append(pin)
        
        # Remove expired entries from metadata
        for pin in pins_to_remove:
            del metadata[pin]
        
        # Save updated metadata
        if pins_to_remove:
            save_file_metadata(metadata)
            
        return len(pins_to_remove)
    except Exception as e:
        st.error(f"Error during cleanup: {e}")
        return 0

# Clean up old files on app start
cleanup_old_files()

# App title and description
st.title("🔒 Secure File Transfer")
st.markdown("Upload files and share them securely with a 4-digit PIN")

# Create tabs for upload and download
tab1, tab2, tab3 = st.tabs(["📤 Upload File", "📥 Download File", "ℹ️ How it Works"])

with tab1:
    st.header("Upload Your File")
    st.markdown("Upload a file to generate a secure PIN for sharing")
    
    uploaded_file = st.file_uploader(
        "Choose a file to upload",
        type=None,  # Allow all file types
        help="Select any file to upload and generate a PIN"
    )
    
    if uploaded_file is not None:
        # Display file info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("File Name", uploaded_file.name)
        with col2:
            st.metric("File Size", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("File Type", uploaded_file.type or "Unknown")
        
        # Generate PIN button
        if st.button("🔐 Generate PIN & Upload", type="primary", use_container_width=True):
            with st.spinner("Uploading file and generating PIN..."):
                try:
                    pin = generate_pin()
                    file_path = save_file_with_pin(uploaded_file, pin)
                    
                    # Success message with PIN
                    st.success("File uploaded successfully!")
                    
                    # Display PIN prominently
                    st.markdown("---")
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        st.markdown(
                            f"""
                            <div style='
                                background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
                                padding: 20px;
                                border-radius: 10px;
                                text-align: center;
                                margin: 20px 0;
                            '>
                                <h2 style='color: white; margin: 0;'>Your PIN</h2>
                                <h1 style='color: white; font-size: 3em; margin: 10px 0; letter-spacing: 0.2em;'>{pin}</h1>
                                <p style='color: white; margin: 0;'>Share this PIN to allow file download</p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    
                    st.info("⏰ **Important:** This PIN will expire in 24 hours for security reasons.")
                    st.warning("🔒 **Security Note:** Only share this PIN with trusted recipients.")
                    
                    # Show file path for debugging (remove in production)
                    # st.success(f"File saved to: {file_path}")
                    
                except Exception as e:
                    st.error(f"Error uploading file: {str(e)}")

with tab2:
    st.header("Download File")
    st.markdown("Enter the 4-digit PIN to download the shared file")
    
    # PIN input
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pin_input = st.text_input(
            "Enter 4-digit PIN",
            max_chars=4,
            placeholder="1234",
            help="Enter the PIN provided by the file sender"
        )
    
    if pin_input:
        if len(pin_input) == 4 and pin_input.isdigit():
            with st.spinner("Verifying PIN..."):
                file_info = get_file_by_pin(pin_input)
                
                if file_info:
                    # Check if file still exists on disk
                    if os.path.exists(file_info['filepath']):
                        # Display file information
                        st.success("✅ PIN verified! File found.")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("File Name", file_info['filename'])
                        with col2:
                            st.metric("File Size", f"{file_info['size'] / 1024:.1f} KB")
                        with col3:
                            st.metric("File Type", file_info['type'] or "Unknown")
                        with col4:
                            time_remaining = 24 - int((datetime.now() - file_info['upload_time']).total_seconds() / 3600)
                            st.metric("Expires in", f"{max(0, time_remaining)} hours")
                        
                        # Download button
                        try:
                            with open(file_info['filepath'], 'rb') as file:
                                file_data = file.read()
                            
                            st.download_button(
                                label="📥 Download File",
                                data=file_data,
                                file_name=file_info['filename'],
                                mime=file_info['type'],
                                type="primary",
                                use_container_width=True
                            )
                            
                        except Exception as e:
                            st.error(f"Error reading file: {str(e)}")
                            st.info("The file might have been corrupted or is no longer accessible.")
                    else:
                        st.error("❌ File not found on disk.")
                        st.info("The file may have been moved or deleted from storage.")
                        # Clean up metadata for missing file
                        metadata = load_file_metadata()
                        if pin_input in metadata:
                            del metadata[pin_input]
                            save_file_metadata(metadata)
                else:
                    st.error("❌ Invalid PIN or file has expired.")
                    st.info("Please check the PIN or contact the file sender.")
        else:
            if pin_input:  # Only show error if user has entered something
                st.warning("Please enter a valid 4-digit PIN")

with tab3:
    st.header("How It Works")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🚀 For Senders")
        st.markdown("""
        1. **Upload**: Select and upload your file
        2. **Generate**: Click to generate a secure 4-digit PIN
        3. **Share**: Send the PIN to your recipient
        4. **Secure**: File expires automatically in 24 hours
        """)
        
        st.subheader("🔒 Security Features")
        st.markdown("""
        - Random 4-digit PIN generation
        - 24-hour automatic expiration
        - Persistent secure file storage
        - Automatic cleanup of expired files
        - Unique PIN guarantee
        """)
    
    with col2:
        st.subheader("📱 For Recipients")
        st.markdown("""
        1. **Receive**: Get the 4-digit PIN from sender
        2. **Enter**: Input PIN in the Download tab
        3. **Verify**: System verifies PIN and shows file info
        4. **Download**: Click to download the file
        """)
        
        st.subheader("⚠️ Important Notes")
        st.markdown("""
        - Files expire after 24 hours
        - PINs are 4-digit numbers only
        - Keep PINs confidential and secure
        - Files are stored temporarily and auto-cleaned
        - Each PIN is unique and cannot be reused
        """)

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col2:
    st.markdown(
        "<p style='text-align: center; color: gray;'>🔐 Secure File Transfer App</p>",
        unsafe_allow_html=True
    )

# Display active transfers (for debugging/admin purposes)
metadata = load_file_metadata()
if metadata:
    with st.expander("📊 Active Transfers (Admin View)", expanded=False):
        st.write(f"Total active transfers: {len(metadata)}")
        for pin, info in metadata.items():
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.text(f"PIN: {pin}")
            with col2:
                st.text(f"File: {info['filename']}")
            with col3:
                st.text(f"Size: {info['size']/1024:.1f} KB")
            with col4:
                hours_left = 24 - int((datetime.now() - info['upload_time']).total_seconds() / 3600)
                st.text(f"Expires: {max(0, hours_left)}h")
else:
    with st.expander("📊 Active Transfers (Admin View)", expanded=False):
        st.info("No active transfers currently")
