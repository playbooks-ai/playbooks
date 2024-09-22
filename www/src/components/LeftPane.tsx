import React from "react";
import PlaybookEditor from "./PlaybookEditor";

interface LeftPaneProps {
  runPlaybook: (code: string) => void;
}

const LeftPane: React.FC<LeftPaneProps> = ({ runPlaybook }) => {
  return <PlaybookEditor runPlaybook={runPlaybook} />;
};

export default LeftPane;
