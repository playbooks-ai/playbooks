# Design considerations
This document outlines the design considerations for the Playbooks system. As we develop the system, we will keep adding to this document to refine the design.

## February 22, 2025
Based on extensive experimentation, we learn what things LLMs are good at and not. Recent LLMs are exceptionally good at procedural thinking. They can make and execute plans that look like a single procedure. We find them weak at nested control flows, managing variables, concurrency, reliably finding triggers to execute, etc. They also get lost in the weeds and lose site of the larger picture when instructed to log their thinking in full detail.

So far, a single LLM call was expected to recurse into playbooks, manage call stack, manage variables, decisions on when the yield control (see the [no-yld](https://github.com/playbooks-ai/playbooks/tree/no-yld) branch where to attempt to give even more yield decision responsibility to the LLM), etc. The interpreter only read the state from the LLM output and executed external calls and called LLM back. With the above understanding of LLM limitations, we will reduce the responsibilities of the LLM and have the interpreter take care of more. Specifically, 
- The LLM will be given a single playbook with a line number to start from and variables.
- Other playbooks are treated as external functions
- The LLM will queue calls to external functions (now both other playbooks and tools)
- The LLM will yield control back when
    - It reaches a line where results of a queued external function are needed 
    - It reaches end of the playbook
- The LLM will not track call stack. That will be handled by the interpreter.
- The LLM will note changes to variables only. The interpreter will manage the list of variables.
- The interpreter will track local and other (global-like) variables.
    - Local variables that those that were passed into the current playbooks or was created in the current playbook.
    - Other variables are local variables accumulated so far as various playbooks executed. Any stale, unneeded variables will be removed.

## Optimizing number of LLM calls
This approach will increase the number of LLM calls required to complete a task. To reduce the number of LLM calls, we will:
- Inline small playbooks where possible. We will experiment to understand how long a playbook can be before LLM starts making mistakes executing it. Then we will make decisions about how called playbooks should be inlined.
- Tail optimization: If playbooks B was called from the return line of another playbook A, once B finishes, we don't need to continue A (it will just return). If we can skip A and go up the call stack, we avoid a wasteful LLM call.

Although more LLM calls will be needed, we expect each call to be lighter in terms of input and output tokens, because the task we are asking the LLM to perform is simpler.

## LLM calls
Three types LLM invocations will be used: 
1. When a new playbook starts (triggered or called)
System prompt will include instructions, list of all available playbooks, few-shot examples (step by step output format, loops, queuing function calls, yield decision, variable updates, unexpected conditions like not having instructions that match state, needing to invoke a different playbook, etc).
User prompt will include variables, the playbook being executed.
** This will be a fresh chat session **

2. When a playbook is resumed in the middle after executing another playbook
Two possibilities (either using the same chat session or starting a new one):
    - **Starting a fresh chat session**
        - System prompt is same
        - User prompt will be same as #1, but with instruction pointer and additional instructions on how to resume.
    - **Reusing existing chat session**
        - We will need to remember LLM chat session ID for each call stack entry so it can be resumed later.
        - User prompt will include log of what happened during the function call, any updated variables, and the instruction pointer to resume from.

3. When current playbook is resumed after external calls
Continue current LLM chat session with just the user prompt.
** This will continue existing chat session **

## Triggers
Triggers need to invoked as needed after each line execution. So far, the LLM bore that responsibility. We found instances where the LLM was unreliable. So, we will move that responsibility to the interpreter as well. Now, how will the interpreter handle triggers?

### Matching triggers
Triggers will be matched using a separate LLM / classifier call which takes the list of triggers available and the current set of variables and possibly already matched triggers. It will return a list of newly matched triggers.

### How to exclude triggers that already matched and have been activated?
- We will keep track of which triggers have been matched and have been activated. 
- When a trigger is matched and activated in the same playbook, the interpreter will not invoke it again.

Potentially, we can instruct to match triggers only for **updated** variables. That will reduce false positives (same trigger matching multiple times)

### What to do for each matched trigger?
Each matched trigger will be treated as a playbook call and added to the call stack. The current playbook's execution will be resumed after the trigger playbook(s) return.

### Matching triggers after each line
This is challenging because we want LLM to execute a set of lines in a single call. The way we will solve this is to watch the LLM's output stream, notice any variable updates and invoke trigger matching. If no triggers are matched, we continue processing the stream. But, if triggers are matched, we ignore rest of the stream and execute the triggers.

This is a bit wasteful as we wasted rest of the LLM's execution, but that is something we will have to live with. One optimization is to cancel LLM request if triggers are matched, in case the request is still ongoing.

## Epilogue
This design is also better aligned with the LLM tool calling ReAct paradigm, where the LLM is given some instructions and may ask for execution of one or more external functions (tools). This approach can be thought of as generalization of tool calling to enable complex program execution, which would be a significant result.