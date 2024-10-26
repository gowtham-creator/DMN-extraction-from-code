import logging
import streamlit as st
import os
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import toml
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
import json
from ruly import DMN
import xml.etree.ElementTree as ET
import graphviz as gv
import tempfile

# Load environment variables
load_dotenv()

# Streamlit page configuration
st.set_page_config(page_title="DMN Table Generator", page_icon=":memo:")

# Load your secrets from a TOML file
secrets = toml.load("secrets.toml")
OPENAI_API_KEY = secrets["OPENAI_API_KEY"]

# Set up Langchain OpenAI chat model
chat_model = ChatOpenAI(model="gpt-4o", temperature=0.0, api_key=OPENAI_API_KEY)
memory = ConversationBufferMemory()
conversation = ConversationChain(memory=memory, llm=chat_model)

# Title
st.title("DMN Rules Chat and Table Generator")

# Initialize chat history if it doesn't exist
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Function to render DMN XML diagram
def render_dmn_diagram(dmn_xml):
    # Parse the DMN XML
    dmn_tree = ET.ElementTree(ET.fromstring(dmn_xml))
    root = dmn_tree.getroot()

    # Create a new Graphviz Digraph
    dot = gv.Digraph()

    # Extract decisions from the XML and add to the diagram
    for decision in root.findall('.//{http://www.omg.org/spec/DMN/20151101/dmn.xsd}decision'):
        decision_id = decision.attrib.get('id', 'unknown')
        decision_name = decision.attrib.get('name', 'unknown')
        dot.node(decision_id, decision_name)

    # Extract the decision table details
    for rule in root.findall('.//{http://www.omg.org/spec/DMN/20151101/dmn.xsd}rule'):
        rule_id = rule.attrib.get('id', 'unknown')
        dot.node(rule_id, "Rule: " + rule_id)

        # Add edges between decisions and rules
        dot.edge(decision_id, rule_id)

    # Save the graph to a temporary file and render it in Streamlit
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        dot.render(temp_file.name, format='svg')
        return temp_file.name


# Function to create .dmn file from decision table data
def generate_dmn(decision_tables, file_name="combined_decision_table.dmn"):
    
    # Format the decision tables for the prompt
    formatted_decision_tables = str(decision_tables).replace("'", "\"")  # Convert single quotes to double quotes
    
    prompt = (
        f"{formatted_decision_tables}"
        f"You are an AI with the capability to generate DMN XML structures. Generate a DMN XML structure based on the following decision tables. "
        f"Return the DMN XML structure formatted correctly without any additional text."
        f"Here is an example of how to generate:\n"
        f"<?xml version=\\\"1.0\\\" encoding=\\\"UTF-8\\\"?>\\n"
        f"<definitions xmlns=\\\"http://www.omg.org/spec/DMN/20151101/dmn.xsd\\\"\\n"
        f"             xmlns:camunda=\\\"http://camunda.org/schema/1.0/dmn\\\"\\n"
        f"             id=\\\"definitions\\\"\\n"
        f"             name=\\\"Decision\\\"\\n"
        f"             namespace=\\\"http://camunda.org/schema/1.0/dmn\\\">\\n"
        f"  <decision id=\\\"decisionTable1\\\" name=\\\"Decision Table 1\\\">\\n"
        f"    <decisionTable id=\\\"decisionTable\\\">\\n"
        f"      <input id=\\\"input1\\\">\\n"
        f"        <inputExpression id=\\\"inputExpression1\\\" typeRef=\\\"number\\\">\\n"
        f"          <text>Age</text>\\n"
        f"        </inputExpression>\\n"
        f"      </input>\\n"
        f"      <output id=\\\"output1\\\" name=\\\"Eligibility\\\" typeRef=\\\"boolean\\\"/>\\n"
        f"      <rule id=\\\"rule1\\\">\\n"
        f"        <inputEntry id=\\\"inputEntry1\\\">\\n"
        f"          <text>&lt; 18</text>\\n"
        f"        </inputEntry>\\n"
        f"        <outputEntry id=\\\"outputEntry1\\\">\\n"
        f"          <text>false</text>\\n"
        f"        </outputEntry>\\n"
        f"      </rule>\\n"
        f"    </decisionTable>\\n"
        f"  </decision>\\n"
        f"</definitions>\"\n"
        f"The output must be a plain string without any code formatting characters."
    )

    
    response = conversation.predict(input=prompt)
    st.markdown("xml \n"+response +" \n")
    
    root = ET.fromstring(response)

    # Write the XML tree to a file
    tree = ET.ElementTree(root)
    tree.write(file_name, xml_declaration=True, encoding='utf-8')

    return response, file_name

# Function to extract decision tables from the OpenAI response
def extract_decision_tables(response):
    try:
        # Assuming the response contains a JSON-like structure
        decision_tables = json.loads(response)
        return decision_tables
    except json.JSONDecodeError:
        st.error("Failed to decode decision tables from the response. Please check the format.")
        return []

# Process chat input
if prompt := st.chat_input("Say Something"):
    with st.chat_message("user"):
        st.markdown(prompt)
        st.session_state.chat_history.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = conversation.predict(input=prompt)
            st.markdown(response)

        st.session_state.chat_history.append({"role": "assistant", "content": response})

        # Check if the prompt requests DMN table generation
        if "generate dmn tables" in prompt.lower():
            # Ask the OpenAI model to generate DMN tables in JSON format
            json_prompt = (
                "You are an AI with the capability to convert various code structures into JSON format. Your task is to generate a JSON representation of the provided code snippet based on the following schema. "
                "Ensure the JSON output adheres to the schema's structure and data types. Return the JSON formatted correctly without any additional text. The output must be a plain string without any code formatting characters."
            )

            with st.spinner("Generating decisions JSON..."):
                json_response = conversation.predict(input=json_prompt)
                st.markdown(json_response)
                dmn_xml, dmn_file_name = generate_dmn(json_response)

                # Notify the user and provide download link
                st.success(f"DMN file '{dmn_file_name}' generated successfully!")
                with open(dmn_file_name, "rb") as f:
                    st.download_button(label="Download DMN File", data=f, file_name=dmn_file_name)
                
                # Render the DMN diagram and display the image
                st.success("Rendering DMN diagram...")
                diagram_path = render_dmn_diagram(dmn_xml)
                st.image(diagram_path)

# Display chat history
if st.session_state.chat_history:
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])