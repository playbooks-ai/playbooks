import { render } from '@testing-library/react';
import GoogleAnalytics from '../GoogleAnalytics';
import { ScriptProps } from 'next/script';

jest.mock('next/script', () => ({
  __esModule: true,
  default: ({ children, ...props }: Partial<ScriptProps>) => {
    return <script {...props}>{children}</script>;
  },
}));

describe('GoogleAnalytics', () => {
  it('renders Google Analytics scripts', () => {
    const { container } = render(<GoogleAnalytics />);
    const scripts = container.getElementsByTagName('script');

    expect(scripts).toHaveLength(2);
    expect(scripts[0]).toHaveAttribute(
      'src',
      'https://www.googletagmanager.com/gtag/js?id=G-V3Q6X91ZXZ'
    );
    expect(scripts[1]).toHaveAttribute('id', 'google-analytics');
  });
});
