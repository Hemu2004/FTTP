# FTTP AI Command Center

AI-powered network planning and costing tool for Fibre-to-the-Premises (FTTP) deployments.

## Features
- **Network Assessment**: AI-driven build classification and cost estimation.
- **Cost Optimization**: Compare standard calculated costs vs. AI-optimized scenarios.
- **Audit Log**: Track all assessments with approval workflows (Review/Approve/Reject).
- **ROI Calculator**: Estimate project returns based on CAPEX, OPEX, and market take-up.
- **Reporting**: Generate PDF costing packs, optimization reports, and ROI summaries.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Variables**:
    Create a `.env` file in the root directory with your API keys:
    ```env
    GROQ_API_KEY=your_key_here
    OPENAI_API_KEY=your_key_here
    mongo_uri=your_mongo_connection_string (optional)
    ```

3.  **Run the App**:
    ```bash
    streamlit run app.py
    ```

## Usage
- Navigate to **"Network Assessment"** to run a new plan.
- Use **"Audit Log"** to review and approve requests.
- Check **"Dashboard"** for daily operational metrics.
