import Image from "next/image";
import Link from "next/link";
import Playground from '@/components/Playground/Playground';
import { Metadata } from 'next';
import styles from './gradient.module.css';

export const metadata: Metadata = {
  title: 'Playbooks AI - Train AI Agents Like Humans',
  description: 'Create AI agents using human-readable and LLM-executed playbooks. Simple, flexible, and powerful platform for training and deploying AI agents.',
  keywords: ['AI agents', 'LLM', 'playbooks', 'artificial intelligence', 'machine learning', 'training'],
  openGraph: {
    title: 'Playbooks AI - Train AI Agents Like Humans',
    description: 'Create AI agents using human-readable and LLM-executed playbooks. Simple, flexible, and powerful platform for training and deploying AI agents.',
    url: 'https://playbooks.ai',
    siteName: 'Playbooks AI',
    images: [
      {
        url: '/playbooks-logo.png',
        width: 600,
        height: 600,
        alt: 'Playbooks AI Logo',
      }
    ],
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Playbooks AI - Train AI Agents Like Humans',
    description: 'Create AI agents using human-readable and LLM-executed playbooks. Simple, flexible, and powerful platform for training and deploying AI agents.',
    images: ['/playbooks-logo.png'],
  },
  robots: {
    index: true,
    follow: true,
  },
  viewport: {
    width: 'device-width',
    initialScale: 1,
  },
  icons: {
    icon: [
      { url: '/playbooks-icon.png', sizes: '600x600' },
      { url: '/playbooks-logo.png', sizes: '600x600' }
    ],
    apple: '/playbooks-logo.png',
  },
};

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-4 md:p-12">
      <div className={styles.gradientBackground}></div>
      {/* Hero Section */}
      <div className="w-full max-w-5xl">
        <div className="flex flex-col items-center text-center mb-16">
          <Image
            src="/playbooks-logo.png"
            alt="Playbooks AI Logo"
            width={128}
            height={128}
            priority
            className="mb-8"
          />
          <h1 className="text-5xl md:text-6xl mb-6">
            Train AI Agents Like Humans
          </h1>
          <p className="text-xl md:text-2xl text-gray-600 dark:text-gray-300 mb-8 max-w-3xl">
            Create AI agents using human-readable and LLM-executed playbooks. Simple, flexible, and powerful.
          </p>
          <div className="flex gap-4">
            {/* <Link
              href="/playground"
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Try Playground
            </Link> */}
            <Link
              href="/docs"
              className="px-6 py-3 border border-gray-300 dark:border-gray-700 rounded-lg hover:border-gray-400 dark:hover:border-gray-600"
            >
              Read Docs
            </Link>
            <a
              className="px-6 py-3 border border-gray-300 dark:border-gray-700 rounded-lg hover:border-gray-400 dark:hover:border-gray-600 flex items-center gap-2 text-gray-500 dark:text-white"
              href="https://github.com/playbooks-ai/playbooks"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Image
                src="/github-mark.svg"
                alt="GitHub"
                width={20}
                height={20}
                priority
                className="dark:hidden"
              />
              <Image
                src="/github-mark-white.svg"
                alt="GitHub"
                width={20}
                height={20}
                priority
                className="hidden dark:block"
              />
              GitHub
            </a>
          </div>
        </div>

        {/* Quick Start Demo */}
        <div className="m-auto mb-16 max-w-6xl">
          <h2 className="text-3xl mb-8 text-center"></h2>
          <Playground className="max-w-6xl mx-auto" />
        </div>

        {/* Why Playbooks */}
        <div className="mb-16">
          <h2 className="text-3xl mb-8">Why Playbooks?</h2>
          <div className="grid md:grid-cols-2 gap-8">
            <div className="space-y-4">
              <p className="text-lg">
                It all started with a simple question - Why can&apos;t we train AI agents just like we train human agents using training material and playbooks?
              </p>
              <p className="text-lg">
                One of the biggest challenges in building AI agents today is specifying and modifying their behavior. Code is too complex for business users, UI builders lack flexibility, and LLMs struggle with complex prompts.
              </p>
            </div>
            <div className="space-y-4">
              <p className="text-lg">
                Playbooks is the perfect middle ground. Write agent behavior in easily readable English-like pseudocode, while the framework handles:
              </p>
              <ul className="list-disc list-inside space-y-2 text-lg">
                <li>Step-by-step control flow</li>
                <li>Internal and external tool integration</li>
                <li>Complex behaviors with multiple playbooks</li>
                <li>Multi-agent communication</li>
                <li>Event-triggered automation</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
