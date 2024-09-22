"use client";

import ChatWidget from "@/components/ChatWidget";
import LeftPane from "@/components/LeftPane";
import { useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
export default function Home() {
  const [activeTab, setActiveTab] = useState("playbook");
  return (
    <div className="m-4 border border-gray-300 rounded-lg">
      {(() => {
        const leftPane = <LeftPane />;
        const chatWidget = <ChatWidget />;

        return (
          <div className="h-[600px]">
            {/* Wide display: Side-by-side with resizable panels */}
            <div className="hidden lg:block h-full">
              <PanelGroup direction="horizontal">
                <Panel defaultSize={70} minSize={30} className="p-2 pl-0">
                  {leftPane}
                </Panel>
                <PanelResizeHandle className="w-2 bg-gray-200 hover:bg-gray-300 cursor-col-resize">
                  <div className="flex items-center justify-center h-full">
                    <div className="w-1 h-8 bg-gray-400 rounded-full"></div>
                  </div>
                </PanelResizeHandle>
                <Panel defaultSize={30} minSize={30} className="p-2">
                  {chatWidget}
                </Panel>
              </PanelGroup>
            </div>

            {/* Narrow display: Tabs */}
            <div className="lg:hidden h-full flex flex-col">
              <div className="flex border-b">
                <div
                  className={`px-4 py-2 cursor-pointer ${
                    activeTab === "playbook" ? "border-b-2 border-blue-500" : ""
                  }`}
                  onClick={() => setActiveTab("playbook")}
                >
                  Playbook
                </div>
                <div
                  className={`px-4 py-2 cursor-pointer ${
                    activeTab === "chat" ? "border-b-2 border-blue-500" : ""
                  }`}
                  onClick={() => setActiveTab("chat")}
                >
                  AI Agent
                </div>
              </div>
              <div className="h-full overflow-auto">
                {activeTab === "playbook" ? leftPane : chatWidget}
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
