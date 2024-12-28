import Image from "next/image";
import Link from "next/link";

export default function Home() {
  return (
    <div className="grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20 font-[family-name:var(--font-geist-sans)]">
      <main className="flex flex-col gap-8 row-start-2 items-center sm:items-start">
        <h1 className="text-6xl font-bold mb-4">Playbooks</h1>
        <p className="text-xl mb-8 text-gray-600 dark:text-gray-300 max-w-2xl text-center sm:text-left">
          A powerful framework for creating and running AI-powered playbooks
        </p>

        <div className="flex gap-4 items-center flex-col sm:flex-row">
          <Link
            className="rounded-full border border-solid border-transparent transition-colors flex items-center justify-center bg-foreground text-background gap-2 hover:bg-[#383838] dark:hover:bg-[#ccc] text-sm sm:text-base h-10 sm:h-12 px-4 sm:px-5"
            href="/playground"
          >
            Try Playground
          </Link>
          <Link
            className="rounded-full border border-solid border-black/[.08] dark:border-white/[.145] transition-colors flex items-center justify-center hover:bg-[#f2f2f2] dark:hover:bg-[#1a1a1a] hover:border-transparent text-sm sm:text-base h-10 sm:h-12 px-4 sm:px-5 sm:min-w-44"
            href="/docs"
          >
            Read Documentation
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12">
          <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-lg">
            <h3 className="text-lg font-semibold mb-2">Easy to Use</h3>
            <p className="text-gray-600 dark:text-gray-400">
              Write playbooks in simple YAML format and let AI do the heavy lifting
            </p>
          </div>
          <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-lg">
            <h3 className="text-lg font-semibold mb-2">Powerful</h3>
            <p className="text-gray-600 dark:text-gray-400">
              Leverage state-of-the-art language models for complex tasks
            </p>
          </div>
          <div className="p-6 border border-gray-200 dark:border-gray-800 rounded-lg">
            <h3 className="text-lg font-semibold mb-2">Flexible</h3>
            <p className="text-gray-600 dark:text-gray-400">
              Support for multiple LLM providers and custom integrations
            </p>
          </div>
        </div>
      </main>

      <footer className="row-start-3 flex gap-6 flex-wrap items-center justify-center">
        <Link
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="/docs"
        >
          Documentation
        </Link>
        <Link
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="/playground"
        >
          Playground
        </Link>
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://github.com/yourusername/playbooks"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub →
        </a>
      </footer>
    </div>
  );
}
