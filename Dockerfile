FROM python:3.11-slim

# --- 1. Environment Config ---
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app
WORKDIR $APP_HOME

# --- 2. System Dependencies & Caching ---
# Install external requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- 3. INFRASTRUCTURE: Nexus SDK Installation (Ticket-ARCH-01) ---
# Copy the SDK source code into the container
COPY nexus_py_sdk/ ./nexus_py_sdk/

# Install the SDK as a system package.
# This ensures 'import nexus' works globally from site-packages.
RUN pip install --no-cache-dir ./nexus_py_sdk

# --- 4. Application Code ---
# Copy the rest of the application (orchestrator.py, etc.)
COPY . .

# Launch the Orchestrator
CMD ["python", "orchestrator.py"]