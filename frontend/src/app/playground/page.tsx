'use client';

import Playground from '@/components/Playground/Playground';

export default function PlaygroundPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-4xl font-bold mb-8">Playbook Playground</h1>
      <Playground />
    </div>
  );
}