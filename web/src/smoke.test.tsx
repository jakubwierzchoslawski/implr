import { render, waitFor } from '@testing-library/react';
import { ReactFlow } from '@xyflow/react';
import { describe, expect, it } from 'vitest';

describe('react flow renders in jsdom', () => {
  it('renders nodes and edges once measured', async () => {
    const nodes = [
      { id: 'a', position: { x: 0, y: 0 }, data: { label: 'A' } },
      { id: 'b', position: { x: 200, y: 0 }, data: { label: 'B' } },
    ];

    const { container } = render(
      <div style={{ width: 800, height: 600 }}>
        <ReactFlow nodes={nodes} edges={[{ id: 'a-b', source: 'a', target: 'b' }]}
                   nodesDraggable={false} panOnDrag={false} />
      </div>,
    );

    await waitFor(() => {
      expect(container.querySelectorAll('.react-flow__node')).toHaveLength(2);
      expect(container.querySelectorAll('.react-flow__edge').length).toBeGreaterThan(0);
    });
  });
});
