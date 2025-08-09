import streamlit as st
import pandas as pd
import os
from datetime import datetime
import io
import boto3
from cryptography.fernet import Fernet
import xlrd

# Cấu hình trang
st.set_page_config(
    page_title="View Report App",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS tùy chỉnh
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)


def main():
    # Header
    st.markdown('<div class="main-header"><h1>📊 View Report Application</h1></div>',
                unsafe_allow_html=True)

    # Sidebar - Login/Navigation
    with st.sidebar:
        st.header("🔐 User Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login", type="primary"):
            if username and password:
                st.success(f"Welcome {username}!")
                st.session_state.logged_in = True
                st.session_state.username = username
            else:
                st.error("Please enter username and password")

        st.divider()

        # Navigation
        if st.session_state.get('logged_in', False):
            st.header("📋 Navigation")
            page = st.selectbox("Choose function:",
                                ["Upload & View Data", "Data Analysis", "Export Report"])

    # Main content area
    if st.session_state.get('logged_in', False):

        # Tab navigation
        tab1, tab2, tab3 = st.tabs(["📁 File Upload", "📊 Data View", "📈 Analysis"])

        with tab1:
            st.header("📁 Upload Excel Files")

            # File uploader
            uploaded_files = st.file_uploader(
                "Choose Excel files",
                accept_multiple_files=True,
                type=['xlsx', 'xls', 'csv']
            )

            if uploaded_files:
                st.success(f"Uploaded {len(uploaded_files)} file(s)")

                # Display file info
                for file in uploaded_files:
                    with st.expander(f"📄 {file.name}"):
                        # File details
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("File Size", f"{file.size} bytes")
                        with col2:
                            st.metric("File Type", file.type)
                        with col3:
                            if st.button(f"Process {file.name}", key=f"process_{file.name}"):
                                st.session_state[f'data_{file.name}'] = file

        with tab2:
            st.header("📊 Data Viewer")

            # Check if any files are uploaded
            uploaded_data = [key for key in st.session_state.keys() if key.startswith('data_')]

            if uploaded_data:
                # File selector
                selected_file_key = st.selectbox(
                    "Select file to view:",
                    uploaded_data,
                    format_func=lambda x: x.replace('data_', '')
                )

                if selected_file_key:
                    file = st.session_state[selected_file_key]

                    try:
                        # Read Excel/CSV
                        if file.name.endswith('.csv'):
                            df = pd.read_csv(file)
                        else:
                            # For Excel files with multiple sheets
                            excel_file = pd.ExcelFile(file)

                            if len(excel_file.sheet_names) > 1:
                                sheet_name = st.selectbox("Select sheet:", excel_file.sheet_names)
                                df = pd.read_excel(file, sheet_name=sheet_name)
                            else:
                                df = pd.read_excel(file)

                        # Display basic info
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Rows", len(df))
                        with col2:
                            st.metric("Total Columns", len(df.columns))
                        with col3:
                            st.metric("Memory Usage", f"{df.memory_usage(deep=True).sum() / 1024:.1f} KB")
                        with col4:
                            st.metric("Data Types", len(df.dtypes.unique()))

                        # Data preview
                        st.subheader("📋 Data Preview")
                        st.dataframe(df, use_container_width=True, height=400)

                        # Column info
                        with st.expander("📝 Column Information"):
                            col_info = pd.DataFrame({
                                'Column': df.columns,
                                'Data Type': df.dtypes,
                                'Non-Null Count': df.count(),
                                'Null Count': df.isnull().sum()
                            })
                            st.dataframe(col_info, use_container_width=True)

                        # Data filtering
                        st.subheader("🔍 Filter Data")

                        # Select columns to filter
                        filter_columns = st.multiselect("Select columns to filter:", df.columns)

                        if filter_columns:
                            filtered_df = df.copy()

                            for col in filter_columns:
                                if df[col].dtype == 'object':
                                    # Text filter
                                    unique_values = df[col].dropna().unique()
                                    selected_values = st.multiselect(f"Filter {col}:", unique_values)
                                    if selected_values:
                                        filtered_df = filtered_df[filtered_df[col].isin(selected_values)]
                                else:
                                    # Numeric filter
                                    min_val, max_val = float(df[col].min()), float(df[col].max())
                                    range_val = st.slider(f"Filter {col}:", min_val, max_val, (min_val, max_val))
                                    filtered_df = filtered_df[
                                        (filtered_df[col] >= range_val[0]) &
                                        (filtered_df[col] <= range_val[1])
                                        ]

                            st.subheader("🎯 Filtered Results")
                            st.dataframe(filtered_df, use_container_width=True)

                            # Download filtered data
                            csv = filtered_df.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Filtered Data",
                                data=csv,
                                file_name=f"filtered_{file.name.split('.')[0]}.csv",
                                mime="text/csv"
                            )

                    except Exception as e:
                        st.error(f"Error reading file: {str(e)}")
            else:
                st.info("👆 Please upload files in the 'File Upload' tab first")

        with tab3:
            st.header("📈 Data Analysis")

            # Check if any data is loaded
            uploaded_data = [key for key in st.session_state.keys() if key.startswith('data_')]

            if uploaded_data:
                selected_file_key = st.selectbox(
                    "Select file for analysis:",
                    uploaded_data,
                    format_func=lambda x: x.replace('data_', ''),
                    key="analysis_file_select"
                )

                if selected_file_key:
                    file = st.session_state[selected_file_key]

                    try:
                        # Read data
                        if file.name.endswith('.csv'):
                            df = pd.read_csv(file)
                        else:
                            df = pd.read_excel(file)

                        # Analysis options
                        analysis_type = st.selectbox(
                            "Select analysis type:",
                            ["Basic Statistics", "Column Analysis", "Data Quality Report"]
                        )

                        if analysis_type == "Basic Statistics":
                            st.subheader("📊 Basic Statistics")

                            # Numeric columns only
                            numeric_columns = df.select_dtypes(include=['number']).columns
                            if len(numeric_columns) > 0:
                                st.dataframe(df[numeric_columns].describe(), use_container_width=True)
                            else:
                                st.warning("No numeric columns found for statistical analysis")

                        elif analysis_type == "Column Analysis":
                            st.subheader("🔍 Column Analysis")

                            selected_column = st.selectbox("Select column to analyze:", df.columns)

                            if selected_column:
                                col1, col2 = st.columns(2)

                                with col1:
                                    st.write("**Column Info:**")
                                    st.write(f"- Data Type: {df[selected_column].dtype}")
                                    st.write(f"- Total Values: {len(df[selected_column])}")
                                    st.write(f"- Non-null Values: {df[selected_column].count()}")
                                    st.write(f"- Null Values: {df[selected_column].isnull().sum()}")
                                    st.write(f"- Unique Values: {df[selected_column].nunique()}")

                                with col2:
                                    if df[selected_column].dtype == 'object':
                                        st.write("**Most Common Values:**")
                                        value_counts = df[selected_column].value_counts().head(10)
                                        st.bar_chart(value_counts)
                                    else:
                                        st.write("**Distribution:**")
                                        st.histogram_chart(df[selected_column].dropna())

                        elif analysis_type == "Data Quality Report":
                            st.subheader("🔍 Data Quality Report")

                            # Missing data analysis
                            missing_data = df.isnull().sum()
                            missing_percent = (missing_data / len(df)) * 100

                            quality_df = pd.DataFrame({
                                'Column': df.columns,
                                'Missing Count': missing_data,
                                'Missing %': missing_percent,
                                'Data Type': df.dtypes
                            })

                            st.dataframe(quality_df, use_container_width=True)

                            # Visualize missing data
                            if missing_data.sum() > 0:
                                st.subheader("📊 Missing Data Visualization")
                                st.bar_chart(missing_data[missing_data > 0])

                    except Exception as e:
                        st.error(f"Error in analysis: {str(e)}")
            else:
                st.info("👆 Please upload files first")

    else:
        # Landing page for non-logged users
        st.markdown("""
        ## 👋 Welcome to View Report Application

        **Features:**
        - 📁 Upload and view Excel/CSV files
        - 📊 Interactive data exploration
        - 📈 Basic data analysis
        - 📱 Mobile-friendly interface
        - 📥 Download filtered results

        **👈 Please login using the sidebar to get started!**
        """)

        # Demo/Sample data
        with st.expander("🎯 Try with Sample Data"):
            if st.button("Load Sample Data"):
                # Create sample data
                sample_data = pd.DataFrame({
                    'Product': ['Item A', 'Item B', 'Item C', 'Item D', 'Item E'],
                    'Quantity': [100, 150, 200, 75, 300],
                    'Price': [10.5, 25.0, 15.75, 8.25, 12.0],
                    'Category': ['Electronics', 'Clothing', 'Electronics', 'Books', 'Clothing'],
                    'Date': pd.date_range('2024-01-01', periods=5)
                })

                st.session_state['data_sample.xlsx'] = sample_data
                st.session_state.logged_in = True
                st.session_state.username = "Demo User"
                st.success("Sample data loaded! Check the tabs above.")
                st.rerun()


# Footer
st.markdown("---")
st.markdown("**💡 Tip:** This app works great on mobile devices! Add to your home screen for app-like experience.")

if __name__ == "__main__":
    main()