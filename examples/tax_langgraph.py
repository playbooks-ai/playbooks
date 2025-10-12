"""
Tax Calculator Multi-Agent System - LangGraph Implementation

True multi-agent system with:
- Separate agent graphs (Host and Tax Accountant)
- Structured LLM outputs (JSON)
- Supervisor pattern for agent coordination
- LangGraph best practices
"""

import operator
import os
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

# ============================================================================
# SHARED STATE
# ============================================================================


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    gross_income: float | None
    tax_rate: float | None
    tax_amount: float | None
    next_agent: str
    final_message: str | None


# ============================================================================
# STRUCTURED OUTPUTS
# ============================================================================


class IncomeExtraction(BaseModel):
    """Structured extraction of gross income from user input."""

    gross_income: float = Field(description="The gross income amount in dollars")
    confidence: float = Field(description="Confidence in extraction (0-1)")


class TaxRateResponse(BaseModel):
    """Structured response from tax accountant."""

    tax_rate: float = Field(description="Tax rate as percentage (e.g., 15 for 15%)")
    reasoning: str = Field(description="Brief explanation of the tax rate")


# ============================================================================
# TOOLS
# ============================================================================


@tool
def calculate_tax(gross_income: float, tax_rate: float) -> float:
    """Calculate tax amount from gross income and tax rate."""
    return gross_income * tax_rate / 100


# ============================================================================
# LLM SETUP
# ============================================================================


def get_llm(structured_output=None):
    """Get LLM instance, optionally with structured output."""
    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4"), temperature=0.7)
    if structured_output:
        return llm.with_structured_output(structured_output)
    return llm


# ============================================================================
# TAX ACCOUNTANT AGENT
# ============================================================================


class TaxAccountantAgent:
    """Independent agent that determines tax rates."""

    def __init__(self):
        self.llm = get_llm()
        self.llm_structured = get_llm(structured_output=TaxRateResponse)

    def determine_tax_rate(self, gross_income: float) -> TaxRateResponse:
        """Determine tax rate based on income level."""
        if gross_income < 100000:
            return TaxRateResponse(
                tax_rate=15.0, reasoning="Income under $100,000 qualifies for 15% rate"
            )
        else:
            return TaxRateResponse(
                tax_rate=25.0, reasoning="Income of $100,000 or more has 25% rate"
            )

    def process_request(self, state: AgentState) -> dict:
        """Process request from host agent."""
        gross_income = state["gross_income"]

        rate_info = self.determine_tax_rate(gross_income)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a knowledgeable tax accountant. Provide the tax rate naturally.",
                ),
                (
                    "user",
                    f"What's the tax rate for a gross income of ${gross_income:,.2f}? "
                    f"The rate is {rate_info.tax_rate}%. Reason: {rate_info.reasoning}",
                ),
            ]
        )

        response = self.llm.invoke(prompt.format_messages())

        return {
            "messages": [response],
            "tax_rate": rate_info.tax_rate,
            "next_agent": "host",
        }


# ============================================================================
# HOST AGENT
# ============================================================================


class HostAgent:
    """Main agent that orchestrates the workflow."""

    def __init__(self):
        self.llm = get_llm()
        self.llm_structured = get_llm(structured_output=IncomeExtraction)

    def ask_for_income(self, state: AgentState) -> dict:
        """Ask user for their gross income."""
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a friendly assistant helping calculate taxes. "
                    "Ask the user for their gross income naturally and conversationally.",
                ),
                ("user", "Start the conversation"),
            ]
        )

        response = self.llm.invoke(prompt.format_messages())

        return {"messages": [response], "next_agent": "user_input"}

    def extract_income(self, state: AgentState) -> dict:
        """Extract gross income from user input using structured output."""
        last_msg = state["messages"][-1]

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Extract the gross income amount from the user's message. "
                    "Look for dollar amounts or numbers that represent income.",
                ),
                ("user", f"User said: {last_msg.content}"),
            ]
        )

        try:
            extraction = self.llm_structured.invoke(prompt.format_messages())

            if extraction.confidence > 0.7:
                return {
                    "gross_income": extraction.gross_income,
                    "next_agent": "tax_accountant",
                }
            else:
                return {"next_agent": "host_ask_income"}
        except Exception:
            return {"next_agent": "host_ask_income"}

    def request_tax_rate(self, state: AgentState) -> dict:
        """Request tax rate from tax accountant."""
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a host agent consulting with a tax accountant. "
                    "Ask about the tax rate naturally and professionally.",
                ),
                (
                    "user",
                    f"Ask the tax accountant about the rate for ${state['gross_income']:,.2f}",
                ),
            ]
        )

        response = self.llm.invoke(prompt.format_messages())

        return {"messages": [response], "next_agent": "tax_accountant"}

    def calculate_and_respond(self, state: AgentState) -> dict:
        """Calculate tax and present result to user."""
        tax_amount = calculate_tax.invoke(
            {"gross_income": state["gross_income"], "tax_rate": state["tax_rate"]}
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a friendly assistant. Tell the user their tax calculation "
                    "results in a natural, helpful way.",
                ),
                (
                    "user",
                    f"Income: ${state['gross_income']:,.2f}, "
                    f"Rate: {state['tax_rate']}%, "
                    f"Tax: ${tax_amount:,.2f}",
                ),
            ]
        )

        response = self.llm.invoke(prompt.format_messages())

        return {
            "messages": [response],
            "tax_amount": tax_amount,
            "final_message": response.content,
            "next_agent": "END",
        }


# ============================================================================
# SUPERVISOR/COORDINATOR
# ============================================================================


class SupervisorAgent:
    """Coordinates between host and tax accountant agents."""

    def __init__(self):
        self.host = HostAgent()
        self.tax_accountant = TaxAccountantAgent()

    def route(self, state: AgentState) -> str:
        """Route to next agent based on state."""
        next_agent = state.get("next_agent", "host_ask_income")

        routing_map = {
            "host_ask_income": "host_ask_income",
            "user_input": "user_input",
            "host_extract": "host_extract",
            "host_request_rate": "host_request_rate",
            "tax_accountant": "tax_accountant",
            "host_final": "host_final",
            "END": END,
        }

        return routing_map.get(next_agent, END)


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================


def build_multi_agent_graph():
    """Build the multi-agent graph with proper agent separation."""

    supervisor = SupervisorAgent()

    workflow = StateGraph(AgentState)

    # Host agent nodes
    workflow.add_node("host_ask_income", supervisor.host.ask_for_income)
    workflow.add_node("host_extract", supervisor.host.extract_income)
    workflow.add_node("host_request_rate", supervisor.host.request_tax_rate)
    workflow.add_node("host_final", supervisor.host.calculate_and_respond)

    # Tax accountant agent node
    workflow.add_node("tax_accountant", supervisor.tax_accountant.process_request)

    # User input node (external)
    def user_input_node(state: AgentState) -> dict:
        return {"next_agent": "host_extract"}

    workflow.add_node("user_input", user_input_node)

    # Set entry point
    workflow.set_entry_point("host_ask_income")

    # Add edges
    workflow.add_conditional_edges("host_ask_income", supervisor.route)
    workflow.add_conditional_edges("user_input", supervisor.route)
    workflow.add_conditional_edges("host_extract", supervisor.route)
    workflow.add_conditional_edges("host_request_rate", supervisor.route)
    workflow.add_conditional_edges("tax_accountant", supervisor.route)
    workflow.add_conditional_edges("host_final", supervisor.route)

    return workflow.compile()


# ============================================================================
# EXECUTION
# ============================================================================


def run_tax_calculator():
    """Run the multi-agent tax calculator interactively."""

    print("=" * 70)
    print("TAX CALCULATOR - LANGGRAPH MULTI-AGENT SYSTEM")
    print("=" * 70)
    print()

    graph = build_multi_agent_graph()

    state = {
        "messages": [],
        "gross_income": None,
        "tax_rate": None,
        "tax_amount": None,
        "next_agent": "host_ask_income",
        "final_message": None,
    }

    # Initial ask - host asks for income
    result = graph.invoke(state)
    if result["messages"]:
        print(f"[HOST]: {result['messages'][-1].content}")

    # Get user input interactively
    user_input = input("\n[YOU]: ").strip()
    result["messages"].append(HumanMessage(content=user_input))
    print()

    # Process income extraction
    result = graph.invoke(result)

    # Request tax rate from accountant
    if result.get("next_agent") == "tax_accountant":
        result = graph.invoke(result)

        # Find tax accountant's response
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and result.get("tax_rate"):
                print(f"[TAX ACCOUNTANT]: {msg.content}\n")
                break

    # Calculate and present final result
    if result.get("next_agent") == "host_final":
        result = graph.invoke(result)
        print(f"[HOST]: {result['messages'][-1].content}\n")

    # Summary
    if result.get("tax_amount"):
        print("=" * 70)
        print("CALCULATION COMPLETE")
        print("=" * 70)
        print(f"Gross Income: ${result['gross_income']:,.2f}")
        print(f"Tax Rate: {result['tax_rate']}%")
        print(f"Tax Amount: ${result['tax_amount']:,.2f}")
        print("=" * 70)

    return result


if __name__ == "__main__":
    run_tax_calculator()
