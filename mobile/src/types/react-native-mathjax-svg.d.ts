declare module 'react-native-mathjax-svg' {
  import { ComponentType } from 'react';

  interface MathJaxProps {
    fontSize?: number;
    color?: string;
    fontCache?: boolean;
    children: string;
  }

  const MathJax: ComponentType<MathJaxProps>;
  export default MathJax;
}
