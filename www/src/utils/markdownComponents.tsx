/* eslint-disable @typescript-eslint/no-unused-vars */
import { Components } from "react-markdown";

export const markdownComponents = {
  h1: ({ node, ...props }) => (
    <h1 className="text-4xl font-bold mt-6 mb-4" {...props} />
  ),
  h2: ({ node, ...props }) => (
    <h2 className="text-3xl font-semibold mt-5 mb-3" {...props} />
  ),
  h3: ({ node, ...props }) => (
    <h3 className="text-2xl font-medium mt-4 mb-2" {...props} />
  ),
  h4: ({ node, ...props }) => (
    <h4 className="text-xl font-medium mt-3 mb-2" {...props} />
  ),
  h5: ({ node, ...props }) => (
    <h5 className="text-lg font-medium mt-2 mb-1" {...props} />
  ),
  h6: ({ node, ...props }) => (
    <h6 className="text-base font-medium mt-2 mb-1" {...props} />
  ),
  p: ({ node, ...props }) => <p className="mb-2" {...props} />,
  ul: ({ node, ...props }) => (
    <ul className="list-disc list-inside mb-2" {...props} />
  ),
  ol: ({ node, ...props }) => (
    <ol className="list-decimal list-inside mb-2" {...props} />
  ),
  li: ({ node, ...props }) => <li className="ml-4" {...props} />,
  blockquote: ({ node, ...props }) => (
    <blockquote
      className="border-l-4 border-gray-300 pl-4 py-2 mb-2"
      {...props}
    />
  ),
  table: ({ node, ...props }) => (
    <table className="border-collapse table-auto w-full mb-2" {...props} />
  ),
  thead: ({ node, ...props }) => <thead className="bg-gray-200" {...props} />,
  tbody: ({ node, ...props }) => <tbody {...props} />,
  tr: ({ node, ...props }) => (
    <tr className="border-b border-gray-300" {...props} />
  ),
  th: ({ node, ...props }) => (
    <th className="border p-2 font-bold" {...props} />
  ),
  td: ({ node, ...props }) => <td className="border p-2" {...props} />,
  code: ({
    node,
    inline,
    className,
    children,
    ...props
  }: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    node: any;
    inline?: boolean;
    className?: string;
    children: React.ReactNode;
  }) => {
    const match = /language-(\w+)/.exec(className || "");
    return !inline && match ? (
      <pre className="bg-gray-100 p-2 rounded overflow-x-auto">
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    ) : (
      <code className="bg-gray-100 px-1 rounded" {...props}>
        {children}
      </code>
    );
  },
} as Components;
