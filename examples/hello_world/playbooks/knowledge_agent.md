# KnowledgeAgent($userquery)

## Trigger
When the user starts a conversation

## Steps
0. $kb = LoadKB(); $current_context = full knowledge base
1. while user query is not answered or no answer is available
    1. if $current_context is a document
        1. Scan the document using ScanDocument($current_context)
        2. If answer is available
            1. return answer
    2. else
        1. $toc = LoadTOC($kb, $current_context)
        2. $subcontext = Find relevant sub context from $toc that may have information to answer user question
        3. $current_context = $subcontext