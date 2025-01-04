import { render, screen } from '@testing-library/react';
import { Footer } from '../Footer';

describe('Footer', () => {
  it('renders footer content', () => {
    render(<Footer />);
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();
  });

  it('displays the correct copyright year', () => {
    render(<Footer />);
    expect(screen.getByText(/Copyright/)).toBeInTheDocument();
  });
});
