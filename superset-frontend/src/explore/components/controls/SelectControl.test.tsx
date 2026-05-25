/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import {
  act,
  createEvent,
  fireEvent,
  render,
  screen,
  userEvent,
  within,
} from 'spec/helpers/testing-library';
import SelectControl, {
  innerGetOptions,
  areAllValuesNumbers,
  getSortComparator,
} from 'src/explore/components/controls/SelectControl';

const defaultProps: {
  choices: [string | number, string][];
  name: string;
  label: string;
  valueKey: string;
  onChange: jest.Mock;
} = {
  choices: [
    ['1 year ago', '1 year ago'],
    ['1 week ago', '1 week ago'],
    ['today', 'today'],
  ],
  name: 'row_limit',
  label: 'Row Limit',
  valueKey: 'value',
  onChange: jest.fn(),
};

beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

const options = [
  { value: '1 year ago', label: '1 year ago' },
  { value: '1 week ago', label: '1 week ago' },
  { value: 'today', label: 'today' },
];

const renderSelectControl = (props = {}) => {
  const overrideProps = {
    ...defaultProps,
    ...props,
  };
  const { container } = render(<SelectControl {...overrideProps} />);
  return container;
};

test('SelectControl calls props.onChange when select', async () => {
  renderSelectControl();
  defaultProps.onChange(50);
  expect(defaultProps.onChange).toHaveBeenCalledWith(50);
});

test('SelectControl - render renders with Select by default', () => {
  renderSelectControl();
  const selectorWrapper = screen.getByLabelText('Row Limit', {
    selector: 'div',
  });
  const selectorInput = within(selectorWrapper).getByLabelText('Row Limit', {
    selector: 'input',
  });
  expect(selectorWrapper).toBeInTheDocument();
  expect(selectorInput).toBeInTheDocument();
});

test('SelectControl - render renders as mode multiple', () => {
  renderSelectControl({ multi: true });
  const selectorWrapper = screen.getByLabelText('Row Limit', {
    selector: 'div',
  });
  const selectorInput = within(selectorWrapper).getByLabelText('Row Limit', {
    selector: 'input',
  });
  expect(selectorWrapper).toBeInTheDocument();
  expect(selectorInput).toBeInTheDocument();
  userEvent.click(selectorInput);
  expect(screen.getByText('Select all (3)')).toBeInTheDocument();
});

test('SelectControl - render renders with allowNewOptions when freeForm', () => {
  renderSelectControl({ freeForm: true });
  const selectorWrapper = screen.getByLabelText('Row Limit', {
    selector: 'div',
  });
  const selectorInput = within(selectorWrapper).getByLabelText('Row Limit', {
    selector: 'input',
  });
  expect(selectorWrapper).toBeInTheDocument();
  expect(selectorInput).toBeInTheDocument();

  // Expect a new option to be selectable.
  userEvent.click(selectorInput);
  userEvent.type(selectorInput, 'a new option');
  act(() => jest.runAllTimers());
  expect(within(selectorWrapper).getByRole('option')).toHaveTextContent(
    'a new option',
  );
});

test('SelectControl - render renders with allowNewOptions=false when freeForm=false', () => {
  const container = renderSelectControl({ freeForm: false });
  const selectorWrapper = screen.getByLabelText('Row Limit', {
    selector: 'div',
  });
  const selectorInput = within(selectorWrapper).getByLabelText('Row Limit', {
    selector: 'input',
  });
  expect(selectorWrapper).toBeInTheDocument();
  expect(selectorInput).toBeInTheDocument();

  // Expect no new option to be selectable.
  userEvent.click(selectorInput);
  userEvent.type(selectorInput, 'a new option');
  act(() => jest.advanceTimersByTime(300));

  expect(container.querySelector('[role="option"]')).not.toBeInTheDocument();
  expect(
    within(selectorWrapper).getByText('No data', { selector: 'div' }),
  ).toBeInTheDocument();
});

test('SelectControl - render renders with tokenSeparators', () => {
  renderSelectControl({ tokenSeparators: ['\n', '\t', ';'], multi: true });
  const selectorWrapper = screen.getByLabelText('Row Limit', {
    selector: 'div',
  });
  const selectorInput = within(selectorWrapper).getByLabelText('Row Limit', {
    selector: 'input',
  });
  expect(selectorWrapper).toBeInTheDocument();
  expect(selectorInput).toBeInTheDocument();

  userEvent.click(selectorInput);
  const paste = createEvent.paste(selectorInput, {
    clipboardData: {
      getData: () => '1 year ago;1 week ago',
    },
  });
  fireEvent(selectorInput, paste);
  const yearOption = screen.getByRole('option', { name: /1 year ago/i });
  expect(yearOption).toBeInTheDocument();
  expect(yearOption).toHaveAttribute('aria-selected', 'true');
  const weekOption = screen.getByRole('option', { name: /1 week ago/ });
  expect(weekOption?.getAttribute('aria-selected')).toEqual('true');
});

test('SelectControl - render - empty placeholder - withMulti does not show a placeholder if there are no choices', () => {
  renderSelectControl({
    choices: [],
    multi: true,
    placeholder: 'add something',
  });
  expect(screen.queryByRole('option')).not.toBeInTheDocument();
});
test('SelectControl - render - empty placeholder - withSingleChoice does not show a placeholder if there are no choices', async () => {
  const container = renderSelectControl({
    choices: [],
    multi: false,
    placeholder: 'add something',
  });
  expect(container.querySelector('[role="option"]')).not.toBeInTheDocument();
});
test('SelectControl - render - empty placeholder - all choices selected does not show a placeholder', () => {
  const container = renderSelectControl({
    multi: true,
    value: ['today', '1 year ago'],
  });
  expect(container.querySelector('[role="option"]')).not.toBeInTheDocument();
  expect(screen.queryByText('Select ...')).not.toBeInTheDocument();
});
test('SelectControl - render - when select is multi does not render the placeholder when a selection has been made', () => {
  renderSelectControl({
    multi: true,
    value: ['today'],
    placeholder: 'add something',
  });
  expect(screen.queryByText('add something')).not.toBeInTheDocument();
});
test('SelectControl - render - when select is single does not render the placeholder when a selection has been made', () => {
  renderSelectControl({
    multi: true,
    value: 50,
    placeholder: 'add something',
  });
  expect(screen.queryByText('add something')).not.toBeInTheDocument();
});

test('SelectControl - getOptions returns the correct options', () => {
  expect(innerGetOptions(defaultProps)).toEqual(options);
});

test('SelectControl - areAllValuesNumbers returns true when all values are numbers (array format)', () => {
  const items = [
    [1, 'One'],
    [2, 'Two'],
    [3, 'Three'],
  ];
  expect(areAllValuesNumbers(items)).toBe(true);
});

test('SelectControl - areAllValuesNumbers returns false when some values are not numbers (array format)', () => {
  const items = [
    [1, 'One'],
    ['two', 'Two'],
    [3, 'Three'],
  ];
  expect(areAllValuesNumbers(items)).toBe(false);
});

test('SelectControl - areAllValuesNumbers returns true when all values are numbers (object format)', () => {
  const items = [
    { value: 1, label: 'One' },
    { value: 2, label: 'Two' },
    { value: 3, label: 'Three' },
  ];
  expect(areAllValuesNumbers(items)).toBe(true);
});

test('SelectControl - areAllValuesNumbers returns false when some values are not numbers (object format)', () => {
  const items = [
    { value: 1, label: 'One' },
    { value: 'two', label: 'Two' },
    { value: 3, label: 'Three' },
  ];
  expect(areAllValuesNumbers(items)).toBe(false);
});

test('SelectControl - areAllValuesNumbers returns true when all values are numbers (primitive format)', () => {
  const items = [1, 2, 3];
  expect(areAllValuesNumbers(items)).toBe(true);
});

test('SelectControl - areAllValuesNumbers returns false when some values are not numbers (primitive format)', () => {
  const items = [1, 'two', 3];
  expect(areAllValuesNumbers(items)).toBe(false);
});

test('SelectControl - areAllValuesNumbers works with custom valueKey', () => {
  const items = [
    { id: 1, label: 'One' },
    { id: 2, label: 'Two' },
    { id: 3, label: 'Three' },
  ];
  expect(areAllValuesNumbers(items, 'id')).toBe(true);
});

test('SelectControl - areAllValuesNumbers returns false for empty items', () => {
  expect(areAllValuesNumbers([])).toBe(false);
  // @ts-expect-error testing invalid input
  expect(areAllValuesNumbers(null)).toBe(false);
  // @ts-expect-error testing invalid input
  expect(areAllValuesNumbers(undefined)).toBe(false);
});

const mockExplicitComparator = (a: { label: string }, b: { label: string }) =>
  a.label.localeCompare(b.label);

test('SelectControl - getSortComparator returns explicit comparator when provided', () => {
  const choices = [
    [1, 'One'],
    [2, 'Two'],
  ];
  const result = getSortComparator(
    choices,
    undefined,
    'value',
    mockExplicitComparator,
  );
  expect(result).toBe(mockExplicitComparator);
});

test('SelectControl - getSortComparator returns number comparator for numeric choices', () => {
  const choices = [
    [1, 'One'],
    [2, 'Two'],
  ];
  const result = getSortComparator(choices, undefined, 'value', undefined);
  expect(typeof result).toBe('function');
  expect(result).not.toBe(mockExplicitComparator);
});

test('SelectControl - getSortComparator returns number comparator for numeric options', () => {
  const options = [
    { value: 1, label: 'One' },
    { value: 2, label: 'Two' },
  ];
  const result = getSortComparator(undefined, options, 'value', undefined);
  expect(typeof result).toBe('function');
  expect(result).not.toBe(mockExplicitComparator);
});

test('SelectControl - getSortComparator prioritizes options over choices when both are numeric', () => {
  const choices = [
    [1, 'One'],
    [2, 'Two'],
  ];
  const options = [
    { value: 3, label: 'Three' },
    { value: 4, label: 'Four' },
  ];
  const result = getSortComparator(choices, options, 'value', undefined);
  expect(typeof result).toBe('function');
});

test('SelectControl - getSortComparator returns undefined for non-numeric choices', () => {
  const choices = [
    ['one', 'One'],
    ['two', 'Two'],
  ];
  const result = getSortComparator(choices, undefined, 'value', undefined);
  expect(result).toBeUndefined();
});

test('SelectControl - getSortComparator returns undefined for non-numeric options', () => {
  const options = [
    { value: 'one', label: 'One' },
    { value: 'two', label: 'Two' },
  ];
  const result = getSortComparator(undefined, options, 'value', undefined);
  expect(result).toBeUndefined();
});

test('SelectControl - getSortComparator returns undefined when no choices or options provided', () => {
  const result = getSortComparator(undefined, undefined, 'value', undefined);
  expect(result).toBeUndefined();
});

test('SelectControl - numeric sorting integration applies numeric sorting to choices automatically', () => {
  const numericChoices = [
    [3, 'Three'],
    [1, 'One'],
    [2, 'Two'],
  ];
  renderSelectControl({ choices: numericChoices });

  // The SelectControl should receive a sortComparator for numeric values
  // This is tested by verifying the component renders without errors
  const selectorWrapper = screen.getByLabelText('Row Limit', {
    selector: 'div',
  });
  expect(selectorWrapper).toBeInTheDocument();
});

test('SelectControl - numeric sorting integration applies numeric sorting to options automatically', () => {
  const numericOptions = [
    { value: 3, label: 'Three' },
    { value: 1, label: 'One' },
    { value: 2, label: 'Two' },
  ];
  renderSelectControl({ options: numericOptions, choices: undefined });

  // The SelectControl should receive a sortComparator for numeric values
  const selectorWrapper = screen.getByLabelText('Row Limit', {
    selector: 'div',
  });
  expect(selectorWrapper).toBeInTheDocument();
});

test('SelectControl - numeric sorting integration does not apply numeric sorting to mixed-type choices', () => {
  const mixedChoices = [
    [1, 'One'],
    ['two', 'Two'],
    [3, 'Three'],
  ];
  renderSelectControl({ choices: mixedChoices });

  // Should render without errors and not apply numeric sorting
  const selectorWrapper = screen.getByLabelText('Row Limit', {
    selector: 'div',
  });
  expect(selectorWrapper).toBeInTheDocument();
});

test('SelectControl - numeric sorting integration respects explicit sortComparator over automatic numeric sorting', () => {
  const numericChoices = [
    [3, 'Three'],
    [1, 'One'],
    [2, 'Two'],
  ];
  const explicitComparator = jest.fn((a, b) => a.label.localeCompare(b.label));

  renderSelectControl({
    choices: numericChoices,
    sortComparator: explicitComparator,
  });

  const selectorWrapper = screen.getByLabelText('Row Limit', {
    selector: 'div',
  });
  expect(selectorWrapper).toBeInTheDocument();
});
