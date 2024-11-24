export function parseJsonLines(buffer: string): {
  jsonObjects: any[];
  remainingBuffer: string;
} {
  const jsonObjects: any[] = [];
  let remainingBuffer = buffer;
  let boundary = remainingBuffer.indexOf("\n");

  while (boundary !== -1) {
    const jsonLine = remainingBuffer.slice(0, boundary);
    remainingBuffer = remainingBuffer.slice(boundary + 1);
    boundary = remainingBuffer.indexOf("\n");

    if (jsonLine) {
      try {
        const jsonObject = JSON.parse(jsonLine);
        jsonObjects.push(jsonObject);
      } catch (e) {
        console.error("Failed to parse JSON line:", jsonLine, e);
      }
    }
  }

  return { jsonObjects, remainingBuffer };
}
