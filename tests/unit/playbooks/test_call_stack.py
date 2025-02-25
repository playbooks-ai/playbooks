from playbooks.call_stack import CallStack, CallStackFrame, InstructionPointer


class TestInstructionPointer:
    def test_initialization(self):
        ip = InstructionPointer("MainPlaybook", "01")
        assert ip.playbook == "MainPlaybook"
        assert ip.line_number == "01"

    def test_str_with_line_number(self):
        ip = InstructionPointer("MainPlaybook", "01")
        assert str(ip) == "MainPlaybook:01"

    def test_str_without_line_number(self):
        ip = InstructionPointer("MainPlaybook", None)
        assert str(ip) == "MainPlaybook"


class TestCallStackFrame:
    def test_initialization(self):
        ip = InstructionPointer("MainPlaybook", "01")
        frame = CallStackFrame(ip, "session123")

        assert frame.instruction_pointer == ip
        assert frame.llm_chat_session_id == "session123"


class TestCallStack:
    def test_initialization(self):
        stack = CallStack()
        assert stack.frames == []

    def test_is_empty(self):
        stack = CallStack()
        assert stack.is_empty() is True

        ip = InstructionPointer("MainPlaybook", "01")
        frame = CallStackFrame(ip, "session123")
        stack.push(frame)

        assert stack.is_empty() is False

    def test_push(self):
        stack = CallStack()
        ip = InstructionPointer("MainPlaybook", "01")
        frame = CallStackFrame(ip, "session123")

        stack.push(frame)
        assert len(stack.frames) == 1
        assert stack.frames[0] == frame

    def test_pop_with_items(self):
        stack = CallStack()
        ip1 = InstructionPointer("MainPlaybook", "01")
        frame1 = CallStackFrame(ip1, "session123")
        ip2 = InstructionPointer("SubPlaybook", "02")
        frame2 = CallStackFrame(ip2, "session456")

        stack.push(frame1)
        stack.push(frame2)

        popped = stack.pop()
        assert popped == frame2
        assert len(stack.frames) == 1
        assert stack.frames[0] == frame1

    def test_pop_empty_stack(self):
        stack = CallStack()
        assert stack.pop() is None

    def test_peek_with_items(self):
        stack = CallStack()
        ip1 = InstructionPointer("MainPlaybook", "01")
        frame1 = CallStackFrame(ip1, "session123")
        ip2 = InstructionPointer("SubPlaybook", "02")
        frame2 = CallStackFrame(ip2, "session456")

        stack.push(frame1)
        stack.push(frame2)

        peeked = stack.peek()
        assert peeked == frame2
        assert len(stack.frames) == 2  # Stack should remain unchanged

    def test_peek_empty_stack(self):
        stack = CallStack()
        assert stack.peek() is None

    def test_repr(self):
        stack = CallStack()
        ip = InstructionPointer("MainPlaybook", "01")
        frame = CallStackFrame(ip, "session123")
        stack.push(frame)

        # The exact format may vary, but it should contain 'CallStack' and 'frames'
        assert "CallStack" in repr(stack)
        assert "frames" in repr(stack)

    def test_str(self):
        stack = CallStack()
        ip = InstructionPointer("MainPlaybook", "01")
        frame = CallStackFrame(ip, "session123")
        stack.push(frame)

        # str should call __repr__
        assert str(stack) == repr(stack)

    def test_to_dict(self):
        stack = CallStack()
        ip1 = InstructionPointer("MainPlaybook", "01")
        frame1 = CallStackFrame(ip1, "session123")
        ip2 = InstructionPointer("SubPlaybook", "02")
        frame2 = CallStackFrame(ip2, "session456")

        stack.push(frame1)
        stack.push(frame2)

        dict_representation = stack.to_dict()
        assert dict_representation == ["MainPlaybook:01", "SubPlaybook:02"]
