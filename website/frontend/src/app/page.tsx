import Image from 'next/image';
import Link from 'next/link';
import Playground from '@/components/Playground/Playground';
import { Metadata, Viewport } from 'next';
import styles from './gradient.module.css';

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export const metadata: Metadata = {
  title: 'Playbooks AI - Train AI Agents Like Humans',
  description:
    'Create AI agents using human-readable and LLM-executed playbooks. Simple, flexible, and powerful platform for training and deploying AI agents.',
  keywords: [
    'AI agents',
    'LLM',
    'playbooks',
    'artificial intelligence',
    'machine learning',
    'training',
  ],
  openGraph: {
    title: 'Playbooks AI - Train AI Agents Like Humans',
    description:
      'Create AI agents using human-readable and LLM-executed playbooks. Simple, flexible, and powerful platform for training and deploying AI agents.',
    url: 'https://playbooks.ai',
    siteName: 'Playbooks AI',
    images: [
      {
        url: '/playbooks-logo.png',
        width: 600,
        height: 600,
        alt: 'Playbooks AI Logo',
      },
    ],
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Playbooks AI - Train AI Agents Like Humans',
    description:
      'Create AI agents using human-readable and LLM-executed playbooks. Simple, flexible, and powerful platform for training and deploying AI agents.',
    images: ['/playbooks-logo.png'],
  },
  robots: {
    index: true,
    follow: true,
  },
  icons: {
    icon: [
      { url: '/playbooks-icon.png', sizes: '600x600' },
      { url: '/playbooks-logo.png', sizes: '600x600' },
    ],
    apple: '/playbooks-logo.png',
  },
};

export default function Home() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-between p-4 md:p-12">
      <div className={styles.gradientBackground}></div>
      {/* Hero Section */}
      <div className="w-full max-w-5xl">
        <div className="mb-16 flex flex-col items-center text-center">
          <Image
            src="/playbooks-logo.png"
            alt="Playbooks AI Logo"
            width={128}
            height={128}
            priority
            className="mb-8"
          />
          <h1 className="mb-6 text-5xl md:text-6xl">Train AI Agents Like Humans</h1>
          <p className="mb-8 max-w-3xl text-xl md:text-2xl">
            Create AI agents using human-readable and LLM-executed playbooks. Simple, flexible, and
            powerful.
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
              className="rounded-lg border border-gray-300 px-6 py-3 hover:border-gray-400 dark:border-gray-700 dark:hover:border-gray-600"
            >
              Read Docs
            </Link>
            <a
              className="flex items-center gap-2 rounded-lg border border-gray-300 px-6 py-3 hover:border-gray-400 dark:border-gray-700 dark:hover:border-gray-600"
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
          <h2 className="mb-8 text-center text-3xl"></h2>
          <Playground className="mx-auto max-w-6xl" />
        </div>

        {/* Why Playbooks */}
        <div className="mb-16">
          <h2 className="mb-8 text-3xl">Why Playbooks?</h2>
          <div className="grid gap-8 md:grid-cols-2">
            <div className="space-y-4">
              <p className="text-lg">
                It all started with a simple question - Why can&apos;t we train AI agents just like
                we train human agents using training material and playbooks?
              </p>
              <p className="text-lg">
                One of the biggest challenges in building AI agents today is specifying and
                modifying their behavior. Code is too complex for business users, UI builders lack
                flexibility, and LLMs struggle with complex prompts.
              </p>
            </div>
            <div className="space-y-4">
              <p className="text-lg">
                Playbooks is the perfect middle ground. Write agent behavior in easily readable
                English-like pseudocode, while the framework handles:
              </p>
              <ul className="list-inside list-disc space-y-2 text-lg">
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
    </div>
  );
}
