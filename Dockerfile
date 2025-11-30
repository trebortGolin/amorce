FROM python:3.11-slim

# --- 1. Environment Config ---
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app
WORKDIR $APP_HOME

# --- 2. System Dependencies & Caching ---
# --- 3. INFRASTRUCTURE: Amorce SDK Installation (Ticket-ARCH-01) ---
# Copy the SDK source code into the container
COPY amorce_py_sdk/ ./amorce_py_sdk/

# Install external requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install the SDK as a system package.
# This ensures 'import amorce' works globally from site-packages.
# (Already installed via requirements.txt if listed there, but keeping explicit install is safe)
RUN pip install --no-cache-dir ./amorce_py_sdk

# --- 4. Application Code ---
# Copy the rest of the application (orchestrator.py, etc.)
COPY . .

# Launch the Orchestrator
CMD ["python", "orchestrator.py"]