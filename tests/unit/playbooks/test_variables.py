from playbooks.call_stack import InstructionPointer
from playbooks.variables import Variable, VariableChangeHistoryEntry, Variables


class TestVariableChangeHistoryEntry:
    def test_initialization(self):
        ip = InstructionPointer("MainPlaybook", "01")
        entry = VariableChangeHistoryEntry(ip, "test value")

        assert entry.instruction_pointer == ip
        assert entry.value == "test value"


class TestVariable:
    def test_initialization(self):
        var = Variable("test_var", "initial value")

        assert var.name == "test_var"
        assert var.value == "initial value"
        assert var.change_history == []

    def test_update(self):
        var = Variable("test_var", "initial value")
        ip = InstructionPointer("MainPlaybook", "01")

        var.update("new value", ip)

        assert var.value == "new value"
        assert len(var.change_history) == 1
        assert var.change_history[0].instruction_pointer == ip
        assert var.change_history[0].value == "new value"

    def test_multiple_updates(self):
        var = Variable("test_var", "initial value")
        ip1 = InstructionPointer("MainPlaybook", "01")
        ip2 = InstructionPointer("MainPlaybook", "02")

        var.update("value 1", ip1)
        var.update("value 2", ip2)

        assert var.value == "value 2"
        assert len(var.change_history) == 2
        assert var.change_history[0].instruction_pointer == ip1
        assert var.change_history[0].value == "value 1"
        assert var.change_history[1].instruction_pointer == ip2
        assert var.change_history[1].value == "value 2"


class TestVariables:
    def test_initialization(self):
        vars = Variables()
        assert vars.variables == {}

    def test_getitem_existing(self):
        vars = Variables()
        vars.variables["test_var"] = Variable("test_var", "test value")

        var = vars["test_var"]
        assert var.name == "test_var"
        assert var.value == "test value"

    def test_getitem_nonexistent(self):
        vars = Variables()
        assert vars["nonexistent"] is None

    def test_setitem_new_variable(self):
        vars = Variables()
        ip = InstructionPointer("MainPlaybook", "01")

        vars.__setitem__("test_var", "test value", ip)

        assert "test_var" in vars.variables
        assert vars.variables["test_var"].name == "test_var"
        assert vars.variables["test_var"].value == "test value"
        assert len(vars.variables["test_var"].change_history) == 1
        assert vars.variables["test_var"].change_history[0].instruction_pointer == ip
        assert vars.variables["test_var"].change_history[0].value == "test value"

    def test_setitem_update_existing(self):
        vars = Variables()
        ip1 = InstructionPointer("MainPlaybook", "01")
        ip2 = InstructionPointer("MainPlaybook", "02")

        # First set
        vars.__setitem__("test_var", "initial value", ip1)

        # Update
        vars.__setitem__("test_var", "new value", ip2)

        assert vars.variables["test_var"].value == "new value"
        assert len(vars.variables["test_var"].change_history) == 2
        assert vars.variables["test_var"].change_history[0].instruction_pointer == ip1
        assert vars.variables["test_var"].change_history[0].value == "initial value"
        assert vars.variables["test_var"].change_history[1].instruction_pointer == ip2
        assert vars.variables["test_var"].change_history[1].value == "new value"

    def test_iter(self):
        vars = Variables()
        vars.variables["var1"] = Variable("var1", "value1")
        vars.variables["var2"] = Variable("var2", "value2")

        var_list = list(vars)
        assert len(var_list) == 2
        assert all(isinstance(var, Variable) for var in var_list)
        assert {var.name for var in var_list} == {"var1", "var2"}

    def test_len(self):
        vars = Variables()
        assert len(vars) == 0

        vars.variables["var1"] = Variable("var1", "value1")
        assert len(vars) == 1

        vars.variables["var2"] = Variable("var2", "value2")
        assert len(vars) == 2

    def test_to_dict(self):
        vars = Variables()
        vars.variables["var1"] = Variable("var1", "value1")
        vars.variables["var2"] = Variable("var2", "value2")

        dict_representation = vars.to_dict()
        assert dict_representation == {"var1": "value1", "var2": "value2"}
