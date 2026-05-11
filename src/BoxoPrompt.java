import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.event.DocumentEvent;
import javax.swing.event.DocumentListener;
import java.awt.*;
import java.awt.datatransfer.StringSelection;
import java.awt.event.ActionEvent;
import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.math.BigDecimal;
import java.math.MathContext;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.text.DecimalFormat;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Scanner;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class BoxoPrompt {
    private static final MathContext MC = MathContext.DECIMAL64;
    private static final DecimalFormat DECIMAL = new DecimalFormat("#,##0.##########");
    private static final LinkedHashMap<String, LinkedHashMap<String, BigDecimal>> UNIT_TABLES = new LinkedHashMap<String, LinkedHashMap<String, BigDecimal>>();
    private static final LinkedHashMap<String, String> UNIT_NOTES = new LinkedHashMap<String, String>();
    private static final LinkedHashMap<String, String> CURRENCIES = new LinkedHashMap<String, String>();
    private static final SecureRandom RANDOM = new SecureRandom();

    static {
        addTable("Weight", "Base unit: gram",
                unit("Grain (gr)", "0.06479891"),
                unit("Dram (dr)", "1.7718451953125"),
                unit("Ounce (oz)", "28.349523125"),
                unit("Pound (lb)", "453.59237"),
                unit("Stone (st)", "6350.29318"),
                unit("US hundredweight (cwt)", "45359.237"),
                unit("UK hundredweight (cwt)", "50802.34544"),
                unit("Milligram (mg)", "0.001"),
                unit("Centigram (cg)", "0.01"),
                unit("Gram (g)", "1"),
                unit("Kilogram (kg)", "1000"),
                unit("Metric ton (t)", "1000000"));

        addTable("Length", "Base unit: meter",
                unit("Millimeter (mm)", "0.001"),
                unit("Centimeter (cm)", "0.01"),
                unit("Meter (m)", "1"),
                unit("Kilometer (km)", "1000"),
                unit("Inch (in)", "0.0254"),
                unit("Foot (ft)", "0.3048"),
                unit("Yard (yd)", "0.9144"),
                unit("Mile (mi)", "1609.344"),
                unit("Nautical mile", "1852"));

        addTable("Data", "Base unit: byte. Binary multiples use 1024.",
                unit("Bit (b)", "0.125"),
                unit("Byte (B)", "1"),
                unit("Kilobyte (KB)", "1024"),
                unit("Megabyte (MB)", "1048576"),
                unit("Gigabyte (GB)", "1073741824"),
                unit("Terabyte (TB)", "1099511627776"),
                unit("Petabyte (PB)", "1125899906842624"));

        addTable("Area", "Base unit: square meter",
                unit("Square millimeter", "0.000001"),
                unit("Square centimeter", "0.0001"),
                unit("Square meter", "1"),
                unit("Square kilometer", "1000000"),
                unit("Square inch", "0.00064516"),
                unit("Square foot", "0.09290304"),
                unit("Square yard", "0.83612736"),
                unit("Acre", "4046.8564224"),
                unit("Hectare", "10000"));

        addTable("Volume", "Base unit: liter",
                unit("Milliliter (ml)", "0.001"),
                unit("Liter (L)", "1"),
                unit("Cubic meter", "1000"),
                unit("US teaspoon", "0.00492892159375"),
                unit("US tablespoon", "0.01478676478125"),
                unit("US fluid ounce", "0.0295735295625"),
                unit("US cup", "0.2365882365"),
                unit("US pint", "0.473176473"),
                unit("US quart", "0.946352946"),
                unit("US gallon", "3.785411784"));

        addTable("Speed", "Base unit: meter per second",
                unit("Meter/second", "1"),
                unit("Kilometer/hour", "0.2777777777777778"),
                unit("Mile/hour", "0.44704"),
                unit("Foot/second", "0.3048"),
                unit("Knot", "0.5144444444444445"));

        addTable("Time", "Base unit: second",
                unit("Millisecond", "0.001"),
                unit("Second", "1"),
                unit("Minute", "60"),
                unit("Hour", "3600"),
                unit("Day", "86400"),
                unit("Week", "604800"),
                unit("Month (30 days)", "2592000"),
                unit("Year (365 days)", "31536000"));

        addCurrencies();
    }

    public static void main(String[] args) {
        if (args.length > 0 && "--cli".equalsIgnoreCase(args[0])) {
            runCli();
            return;
        }
        try {
            UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName());
        } catch (Exception ignored) {
            // Swing will fall back to the default look and feel.
        }
        SwingUtilities.invokeLater(new Runnable() {
            public void run() {
                new BoxoPromptApp().show();
            }
        });
    }

    private static void runCli() {
        Scanner scanner = new Scanner(System.in);
        System.out.println("BOXOPROMPT 2026 - KULEDEVER");
        System.out.println("GUI build ready. Run without --cli to open the desktop utility.");
        System.out.println("Commands: help, units, leave");
        while (true) {
            System.out.print("BOXOPROMPT> ");
            String command = scanner.nextLine().trim().toLowerCase(Locale.ROOT);
            if ("leave".equals(command)) {
                System.out.println("THANK YOU FOR TRYING BOXOPROMPT, ENJOY YOUR DAY ;)");
                return;
            } else if ("help".equals(command)) {
                System.out.println("help - show commands");
                System.out.println("units - list converter categories");
                System.out.println("leave - exit");
            } else if ("units".equals(command)) {
                for (String name : UNIT_TABLES.keySet()) {
                    System.out.println("- " + name);
                }
            } else if (command.length() == 0) {
                continue;
            } else {
                System.out.println("Open the GUI for the full toolset, or type help.");
            }
        }
    }

    private static class BoxoPromptApp {
        private JFrame frame;
        private JLabel status;

        void show() {
            frame = new JFrame("BOXOPROMPT Utility Suite");
            frame.setDefaultCloseOperation(WindowConstants.EXIT_ON_CLOSE);
            frame.setMinimumSize(new Dimension(1040, 720));

            JTabbedPane tabs = new JTabbedPane();
            tabs.setFont(tabs.getFont().deriveFont(Font.BOLD, 13f));
            tabs.addTab("Units", new UnitPanel());
            tabs.addTab("Currencies", new CurrencyPanel());
            tabs.addTab("Text", new TextPanel());
            tabs.addTab("Numbers", new NumbersPanel());
            tabs.addTab("Developer", new DeveloperPanel());
            tabs.addTab("Hashes", new HashPanel());
            tabs.addTab("Passwords", new PasswordPanel());
            tabs.addTab("Finance", new FinancePanel());
            tabs.addTab("Dates", new DatePanel());
            tabs.addTab("Color", new ColorPanel());
            tabs.addTab("Files", new FilePanel());
            tabs.addTab("Notes", new NotesPanel());

            JPanel root = new JPanel(new BorderLayout());
            root.setBackground(new Color(244, 247, 251));
            root.add(header(), BorderLayout.NORTH);
            root.add(tabs, BorderLayout.CENTER);
            status = new JLabel("Free utility suite. Local-first tools. Currency rates use a free public endpoint only when you request them.");
            status.setBorder(new EmptyBorder(8, 14, 8, 14));
            root.add(status, BorderLayout.SOUTH);

            frame.setContentPane(root);
            frame.setLocationRelativeTo(null);
            frame.setVisible(true);
        }

        private JPanel header() {
            JPanel panel = new JPanel(new BorderLayout());
            panel.setBackground(new Color(15, 35, 63));
            panel.setBorder(new EmptyBorder(18, 22, 18, 22));
            JLabel title = new JLabel("BOXOPROMPT");
            title.setForeground(Color.WHITE);
            title.setFont(title.getFont().deriveFont(Font.BOLD, 25f));
            JLabel subtitle = new JLabel("Free desktop utility suite: converters, text, numbers, developer tools, hashes, passwords, finance, dates, files");
            subtitle.setForeground(new Color(205, 222, 241));
            JPanel copy = new JPanel(new GridLayout(2, 1));
            copy.setOpaque(false);
            copy.add(title);
            copy.add(subtitle);
            JButton about = new JButton("About");
            about.addActionListener(new AbstractAction() {
                public void actionPerformed(ActionEvent e) {
                    JOptionPane.showMessageDialog(frame,
                            "BOXOPROMPT 2026 - KULEDEVER\n\nNo paid APIs. No external libraries. No subscriptions.\nBuilt with Java Swing and standard Java libraries.",
                            "About BOXOPROMPT", JOptionPane.INFORMATION_MESSAGE);
                }
            });
            panel.add(copy, BorderLayout.WEST);
            panel.add(about, BorderLayout.EAST);
            return panel;
        }
    }

    private static class UnitPanel extends JPanel {
        private JComboBox<String> category;
        private JComboBox<String> from;
        private JComboBox<String> to;
        private JTextField amount;
        private JLabel result;
        private JLabel note;

        UnitPanel() {
            super(new BorderLayout(14, 14));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            category = new JComboBox<String>(UNIT_TABLES.keySet().toArray(new String[0]));
            from = new JComboBox<String>();
            to = new JComboBox<String>();
            amount = new JTextField("1");
            result = resultLabel();
            note = new JLabel();

            JPanel controls = gridPanel(5);
            controls.add(labeled("Category", category));
            controls.add(labeled("Amount", amount));
            controls.add(labeled("From", from));
            controls.add(labeled("To", to));
            JButton swap = new JButton("Swap");
            controls.add(wrapButton("Quick action", swap));
            add(controls, BorderLayout.NORTH);
            add(centerResult(result, note), BorderLayout.CENTER);

            category.addActionListener(new AbstractAction() {
                public void actionPerformed(ActionEvent e) {
                    loadUnits();
                }
            });
            swap.addActionListener(new AbstractAction() {
                public void actionPerformed(ActionEvent e) {
                    int a = from.getSelectedIndex();
                    from.setSelectedIndex(to.getSelectedIndex());
                    to.setSelectedIndex(a);
                    convert();
                }
            });
            DocumentListener listener = simpleListener(new Runnable() { public void run() { convert(); } });
            amount.getDocument().addDocumentListener(listener);
            from.addActionListener(new AbstractAction() { public void actionPerformed(ActionEvent e) { convert(); } });
            to.addActionListener(new AbstractAction() { public void actionPerformed(ActionEvent e) { convert(); } });
            loadUnits();
        }

        private void loadUnits() {
            String selected = (String) category.getSelectedItem();
            List<String> units = new ArrayList<String>(UNIT_TABLES.get(selected).keySet());
            from.setModel(new DefaultComboBoxModel<String>(units.toArray(new String[0])));
            to.setModel(new DefaultComboBoxModel<String>(units.toArray(new String[0])));
            if (units.size() > 1) {
                to.setSelectedIndex(1);
            }
            note.setText(UNIT_NOTES.get(selected));
            convert();
        }

        private void convert() {
            try {
                BigDecimal value = new BigDecimal(amount.getText().trim(), MC);
                String selected = (String) category.getSelectedItem();
                String fromUnit = (String) from.getSelectedItem();
                String toUnit = (String) to.getSelectedItem();
                BigDecimal base = value.multiply(UNIT_TABLES.get(selected).get(fromUnit), MC);
                BigDecimal converted = base.divide(UNIT_TABLES.get(selected).get(toUnit), MC);
                result.setText(format(value) + " " + fromUnit + " = " + format(converted) + " " + toUnit);
            } catch (Exception ex) {
                result.setText("Enter a valid number.");
            }
        }
    }

    private static class CurrencyPanel extends JPanel {
        private JTextField amount;
        private JComboBox<String> from;
        private JComboBox<String> to;
        private JLabel result;
        private JLabel source;

        CurrencyPanel() {
            super(new BorderLayout(14, 14));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            amount = new JTextField("100");
            from = new JComboBox<String>(currencyOptions());
            to = new JComboBox<String>(currencyOptions());
            from.setSelectedItem("USD - US Dollar");
            to.setSelectedItem("EUR - Euro");
            result = resultLabel();
            source = new JLabel("Uses the free Frankfurter public API when online. No API key, no paid service.");
            JButton convert = new JButton("Fetch free rate");
            convert.addActionListener(new AbstractAction() {
                public void actionPerformed(ActionEvent e) {
                    convert.setEnabled(false);
                    result.setText("Fetching...");
                    new Thread(new Runnable() {
                        public void run() {
                            final String message = convertCurrency();
                            SwingUtilities.invokeLater(new Runnable() {
                                public void run() {
                                    result.setText(message);
                                    convert.setEnabled(true);
                                }
                            });
                        }
                    }).start();
                }
            });

            JPanel controls = gridPanel(4);
            controls.add(labeled("Amount", amount));
            controls.add(labeled("From", from));
            controls.add(labeled("To", to));
            controls.add(wrapButton("Action", convert));
            add(controls, BorderLayout.NORTH);
            add(centerResult(result, source), BorderLayout.CENTER);
        }

        private String convertCurrency() {
            try {
                BigDecimal value = new BigDecimal(amount.getText().trim(), MC);
                String fromCode = codeFromOption((String) from.getSelectedItem());
                String toCode = codeFromOption((String) to.getSelectedItem());
                if (fromCode.equals(toCode)) {
                    return format(value) + " " + fromCode + " = " + format(value) + " " + toCode;
                }
                BigDecimal converted = fetchCurrency(value, fromCode, toCode);
                return format(value) + " " + fromCode + " = " + format(converted) + " " + toCode;
            } catch (Exception ex) {
                return "Could not fetch the rate. Check your connection, then try again.";
            }
        }
    }

    private static class TextPanel extends JPanel {
        private JTextArea input;
        private JTextArea output;
        private JLabel stats;

        TextPanel() {
            super(new BorderLayout(12, 12));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            input = new JTextArea(10, 40);
            output = new JTextArea(10, 40);
            output.setEditable(false);
            stats = new JLabel("Ready");

            JPanel buttons = new JPanel(new FlowLayout(FlowLayout.LEFT));
            addButton(buttons, "UPPER", new Runnable() { public void run() { setOutput(input.getText().toUpperCase(Locale.ROOT)); } });
            addButton(buttons, "lower", new Runnable() { public void run() { setOutput(input.getText().toLowerCase(Locale.ROOT)); } });
            addButton(buttons, "Title Case", new Runnable() { public void run() { setOutput(titleCase(input.getText())); } });
            addButton(buttons, "Sort lines", new Runnable() { public void run() { setOutput(sortLines(input.getText(), false)); } });
            addButton(buttons, "Unique lines", new Runnable() { public void run() { setOutput(uniqueLines(input.getText())); } });
            addButton(buttons, "Trim lines", new Runnable() { public void run() { setOutput(trimLines(input.getText())); } });
            addButton(buttons, "Base64 encode", new Runnable() { public void run() { setOutput(java.util.Base64.getEncoder().encodeToString(input.getText().getBytes(StandardCharsets.UTF_8))); } });
            addButton(buttons, "Base64 decode", new Runnable() { public void run() { decodeBase64(); } });
            addButton(buttons, "URL encode", new Runnable() { public void run() { setOutput(urlEncode(input.getText())); } });
            addButton(buttons, "Copy output", new Runnable() { public void run() { copy(output.getText()); } });

            JSplitPane split = new JSplitPane(JSplitPane.HORIZONTAL_SPLIT, scroll(input), scroll(output));
            split.setResizeWeight(0.5);
            add(buttons, BorderLayout.NORTH);
            add(split, BorderLayout.CENTER);
            add(stats, BorderLayout.SOUTH);
            input.getDocument().addDocumentListener(simpleListener(new Runnable() { public void run() { updateStats(); } }));
            updateStats();
        }

        private void setOutput(String value) {
            output.setText(value);
            updateStats();
        }

        private void decodeBase64() {
            try {
                setOutput(new String(java.util.Base64.getDecoder().decode(input.getText().trim()), StandardCharsets.UTF_8));
            } catch (IllegalArgumentException ex) {
                setOutput("Invalid Base64 input.");
            }
        }

        private void updateStats() {
            String text = input.getText();
            int words = text.trim().isEmpty() ? 0 : text.trim().split("\\s+").length;
            int lines = text.isEmpty() ? 0 : text.split("\\R", -1).length;
            stats.setText("Characters: " + text.length() + " | Words: " + words + " | Lines: " + lines);
        }
    }

    private static class NumbersPanel extends JPanel {
        private JTextField percentValue = new JTextField("15");
        private JTextField percentBase = new JTextField("250");
        private JLabel percentResult = resultLabel();
        private JTextField baseInput = new JTextField("255");
        private JComboBox<String> fromBase = new JComboBox<String>(new String[]{"2", "8", "10", "16", "36"});
        private JComboBox<String> toBase = new JComboBox<String>(new String[]{"2", "8", "10", "16", "36"});
        private JLabel baseResult = resultLabel();
        private JTextField min = new JTextField("1");
        private JTextField max = new JTextField("100");
        private JLabel randomResult = resultLabel();

        NumbersPanel() {
            super(new GridLayout(3, 1, 12, 12));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            toBase.setSelectedItem("16");

            JPanel percent = card("Percentage calculator");
            percent.add(labeled("Percent", percentValue));
            percent.add(labeled("Of value", percentBase));
            addButton(percent, "Calculate", new Runnable() { public void run() { calcPercent(); } });
            percent.add(percentResult);

            JPanel bases = card("Base converter");
            bases.add(labeled("Number", baseInput));
            bases.add(labeled("From base", fromBase));
            bases.add(labeled("To base", toBase));
            addButton(bases, "Convert", new Runnable() { public void run() { convertBase(); } });
            bases.add(baseResult);

            JPanel random = card("Random number generator");
            random.add(labeled("Minimum", min));
            random.add(labeled("Maximum", max));
            addButton(random, "Generate", new Runnable() { public void run() { generateRandomNumber(); } });
            random.add(randomResult);

            add(percent);
            add(bases);
            add(random);
            calcPercent();
            convertBase();
            generateRandomNumber();
        }

        private void calcPercent() {
            try {
                BigDecimal percent = new BigDecimal(percentValue.getText().trim(), MC);
                BigDecimal base = new BigDecimal(percentBase.getText().trim(), MC);
                BigDecimal answer = base.multiply(percent, MC).divide(new BigDecimal("100"), MC);
                percentResult.setText(format(percent) + "% of " + format(base) + " = " + format(answer));
            } catch (Exception ex) {
                percentResult.setText("Enter valid percentage numbers.");
            }
        }

        private void convertBase() {
            try {
                int source = Integer.parseInt((String) fromBase.getSelectedItem());
                int target = Integer.parseInt((String) toBase.getSelectedItem());
                long value = Long.parseLong(baseInput.getText().trim(), source);
                baseResult.setText(Long.toString(value, target).toUpperCase(Locale.ROOT));
            } catch (Exception ex) {
                baseResult.setText("Enter a valid integer for the selected base.");
            }
        }

        private void generateRandomNumber() {
            try {
                int low = Integer.parseInt(min.getText().trim());
                int high = Integer.parseInt(max.getText().trim());
                if (high < low) {
                    int swap = low;
                    low = high;
                    high = swap;
                }
                int value = low + RANDOM.nextInt(high - low + 1);
                randomResult.setText(String.valueOf(value));
            } catch (Exception ex) {
                randomResult.setText("Enter valid whole numbers.");
            }
        }
    }

    private static class DeveloperPanel extends JPanel {
        private JTextArea input = new JTextArea(8, 50);
        private JTextArea output = new JTextArea(12, 50);
        private JTextField epochInput = new JTextField(String.valueOf(System.currentTimeMillis() / 1000L));
        private JLabel epochResult = resultLabel();

        DeveloperPanel() {
            super(new BorderLayout(12, 12));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            output.setEditable(false);

            JPanel actions = new JPanel(new FlowLayout(FlowLayout.LEFT));
            addButton(actions, "Generate UUIDs", new Runnable() { public void run() { generateUuids(); } });
            addButton(actions, "Escape Java string", new Runnable() { public void run() { output.setText(escapeJava(input.getText())); } });
            addButton(actions, "Unescape Java string", new Runnable() { public void run() { output.setText(unescapeJava(input.getText())); } });
            addButton(actions, "URL decode", new Runnable() { public void run() { output.setText(urlDecode(input.getText())); } });
            addButton(actions, "Copy output", new Runnable() { public void run() { copy(output.getText()); } });

            JPanel epoch = new JPanel(new BorderLayout(8, 8));
            epoch.setBorder(BorderFactory.createTitledBorder("Unix time"));
            epoch.add(labeled("Epoch seconds", epochInput), BorderLayout.CENTER);
            JButton convert = new JButton("Convert");
            convert.addActionListener(new AbstractAction() { public void actionPerformed(ActionEvent e) { convertEpoch(); } });
            epoch.add(convert, BorderLayout.EAST);
            epoch.add(epochResult, BorderLayout.SOUTH);

            JSplitPane split = new JSplitPane(JSplitPane.HORIZONTAL_SPLIT, scroll(input), scroll(output));
            split.setResizeWeight(0.5);
            add(actions, BorderLayout.NORTH);
            add(split, BorderLayout.CENTER);
            add(epoch, BorderLayout.SOUTH);
            generateUuids();
            convertEpoch();
        }

        private void generateUuids() {
            StringBuilder text = new StringBuilder();
            for (int i = 0; i < 8; i++) {
                text.append(UUID.randomUUID().toString()).append('\n');
            }
            output.setText(text.toString());
        }

        private void convertEpoch() {
            try {
                long seconds = Long.parseLong(epochInput.getText().trim());
                LocalDateTime date = LocalDateTime.ofInstant(new java.util.Date(seconds * 1000L).toInstant(), java.time.ZoneId.systemDefault());
                epochResult.setText(date.format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
            } catch (Exception ex) {
                epochResult.setText("Enter valid epoch seconds.");
            }
        }
    }

    private static class HashPanel extends JPanel {
        private JTextArea input;
        private JTextArea output;
        private File selectedFile;

        HashPanel() {
            super(new BorderLayout(12, 12));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            input = new JTextArea(8, 60);
            output = new JTextArea(12, 60);
            output.setEditable(false);
            JPanel buttons = new JPanel(new FlowLayout(FlowLayout.LEFT));
            addButton(buttons, "Hash text", new Runnable() { public void run() { hashText(); } });
            addButton(buttons, "Choose file", new Runnable() { public void run() { chooseFile(); } });
            addButton(buttons, "Hash file", new Runnable() { public void run() { hashFile(); } });
            addButton(buttons, "Copy", new Runnable() { public void run() { copy(output.getText()); } });
            add(buttons, BorderLayout.NORTH);
            add(scroll(input), BorderLayout.CENTER);
            add(scroll(output), BorderLayout.SOUTH);
        }

        private void hashText() {
            byte[] bytes = input.getText().getBytes(StandardCharsets.UTF_8);
            output.setText(hashReport(bytes));
        }

        private void chooseFile() {
            JFileChooser chooser = new JFileChooser();
            if (chooser.showOpenDialog(this) == JFileChooser.APPROVE_OPTION) {
                selectedFile = chooser.getSelectedFile();
                output.setText("Selected: " + selectedFile.getAbsolutePath());
            }
        }

        private void hashFile() {
            if (selectedFile == null) {
                output.setText("Choose a file first.");
                return;
            }
            try {
                output.setText(hashReport(selectedFile));
            } catch (Exception ex) {
                output.setText("Could not hash file: " + ex.getMessage());
            }
        }
    }

    private static class PasswordPanel extends JPanel {
        private JSpinner length;
        private JCheckBox upper;
        private JCheckBox lower;
        private JCheckBox digits;
        private JCheckBox symbols;
        private JTextArea output;

        PasswordPanel() {
            super(new BorderLayout(12, 12));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            length = new JSpinner(new SpinnerNumberModel(24, 6, 128, 1));
            upper = new JCheckBox("Uppercase", true);
            lower = new JCheckBox("Lowercase", true);
            digits = new JCheckBox("Digits", true);
            symbols = new JCheckBox("Symbols", true);
            output = new JTextArea(14, 60);
            output.setEditable(false);
            JPanel controls = new JPanel(new FlowLayout(FlowLayout.LEFT));
            controls.add(new JLabel("Length"));
            controls.add(length);
            controls.add(upper);
            controls.add(lower);
            controls.add(digits);
            controls.add(symbols);
            addButton(controls, "Generate 10", new Runnable() { public void run() { generate(); } });
            addButton(controls, "Copy all", new Runnable() { public void run() { copy(output.getText()); } });
            add(controls, BorderLayout.NORTH);
            add(scroll(output), BorderLayout.CENTER);
            generate();
        }

        private void generate() {
            String chars = "";
            if (upper.isSelected()) chars += "ABCDEFGHJKLMNPQRSTUVWXYZ";
            if (lower.isSelected()) chars += "abcdefghijkmnopqrstuvwxyz";
            if (digits.isSelected()) chars += "23456789";
            if (symbols.isSelected()) chars += "!@#$%^&*_-+=?";
            if (chars.isEmpty()) {
                output.setText("Select at least one character group.");
                return;
            }
            int count = ((Number) length.getValue()).intValue();
            StringBuilder text = new StringBuilder();
            for (int i = 0; i < 10; i++) {
                for (int j = 0; j < count; j++) {
                    text.append(chars.charAt(RANDOM.nextInt(chars.length())));
                }
                text.append('\n');
            }
            output.setText(text.toString());
        }
    }

    private static class FinancePanel extends JPanel {
        private JTextField principal = new JTextField("250000");
        private JTextField rate = new JTextField("7.5");
        private JTextField years = new JTextField("30");
        private JTextField bill = new JTextField("45.00");
        private JTextField tip = new JTextField("15");
        private JTextField people = new JTextField("2");
        private JLabel loanResult = resultLabel();
        private JLabel tipResult = resultLabel();

        FinancePanel() {
            super(new GridLayout(2, 1, 12, 12));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            JPanel loan = card("Loan calculator");
            loan.add(labeled("Principal", principal));
            loan.add(labeled("APR %", rate));
            loan.add(labeled("Years", years));
            JButton loanButton = new JButton("Calculate");
            loanButton.addActionListener(new AbstractAction() { public void actionPerformed(ActionEvent e) { calcLoan(); } });
            loan.add(loanButton);
            loan.add(loanResult);

            JPanel tipCard = card("Tip and split calculator");
            tipCard.add(labeled("Bill", bill));
            tipCard.add(labeled("Tip %", tip));
            tipCard.add(labeled("People", people));
            JButton tipButton = new JButton("Calculate");
            tipButton.addActionListener(new AbstractAction() { public void actionPerformed(ActionEvent e) { calcTip(); } });
            tipCard.add(tipButton);
            tipCard.add(tipResult);
            add(loan);
            add(tipCard);
            calcLoan();
            calcTip();
        }

        private void calcLoan() {
            try {
                double p = Double.parseDouble(principal.getText());
                double monthlyRate = Double.parseDouble(rate.getText()) / 100.0 / 12.0;
                int months = (int) Math.round(Double.parseDouble(years.getText()) * 12.0);
                double payment = monthlyRate == 0 ? p / months : p * monthlyRate / (1.0 - Math.pow(1.0 + monthlyRate, -months));
                double total = payment * months;
                loanResult.setText("Monthly: " + money(payment) + " | Total interest: " + money(total - p));
            } catch (Exception ex) {
                loanResult.setText("Enter valid loan numbers.");
            }
        }

        private void calcTip() {
            try {
                double b = Double.parseDouble(bill.getText());
                double t = Double.parseDouble(tip.getText()) / 100.0;
                int p = Math.max(1, Integer.parseInt(people.getText()));
                double total = b * (1.0 + t);
                tipResult.setText("Total: " + money(total) + " | Each person: " + money(total / p));
            } catch (Exception ex) {
                tipResult.setText("Enter valid bill numbers.");
            }
        }
    }

    private static class DatePanel extends JPanel {
        private JTextField start = new JTextField(LocalDate.now().toString());
        private JTextField end = new JTextField(LocalDate.now().plusDays(30).toString());
        private JSpinner addDays = new JSpinner(new SpinnerNumberModel(14, -100000, 100000, 1));
        private JLabel result = resultLabel();

        DatePanel() {
            super(new BorderLayout(12, 12));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            JPanel controls = gridPanel(4);
            controls.add(labeled("Start date", start));
            controls.add(labeled("End date", end));
            controls.add(labeled("Add days", addDays));
            JButton calc = new JButton("Calculate");
            calc.addActionListener(new AbstractAction() { public void actionPerformed(ActionEvent e) { calculate(); } });
            controls.add(wrapButton("Action", calc));
            add(controls, BorderLayout.NORTH);
            add(centerResult(result, new JLabel("Use ISO dates like 2026-05-10.")), BorderLayout.CENTER);
            calculate();
        }

        private void calculate() {
            try {
                LocalDate a = LocalDate.parse(start.getText().trim());
                LocalDate b = LocalDate.parse(end.getText().trim());
                long days = ChronoUnit.DAYS.between(a, b);
                LocalDate plus = a.plusDays(((Number) addDays.getValue()).longValue());
                result.setText(days + " days between dates | Start plus days = " + plus);
            } catch (Exception ex) {
                result.setText("Enter valid dates.");
            }
        }
    }

    private static class ColorPanel extends JPanel {
        private JTextField hex = new JTextField("#0F4C81");
        private JSlider red = new JSlider(0, 255, 15);
        private JSlider green = new JSlider(0, 255, 76);
        private JSlider blue = new JSlider(0, 255, 129);
        private JPanel swatch = new JPanel();
        private JLabel result = resultLabel();

        ColorPanel() {
            super(new BorderLayout(12, 12));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            JPanel controls = gridPanel(4);
            controls.add(labeled("HEX", hex));
            controls.add(labeled("Red", red));
            controls.add(labeled("Green", green));
            controls.add(labeled("Blue", blue));
            swatch.setPreferredSize(new Dimension(160, 160));
            JButton applyHex = new JButton("Apply HEX");
            applyHex.addActionListener(new AbstractAction() { public void actionPerformed(ActionEvent e) { fromHex(); } });
            ChangeForwarder forwarder = new ChangeForwarder();
            red.addChangeListener(forwarder);
            green.addChangeListener(forwarder);
            blue.addChangeListener(forwarder);
            add(controls, BorderLayout.NORTH);
            JPanel center = new JPanel(new BorderLayout(12, 12));
            center.add(swatch, BorderLayout.WEST);
            center.add(centerResult(result, new JLabel("Convert between HEX and RGB.")), BorderLayout.CENTER);
            center.add(applyHex, BorderLayout.SOUTH);
            add(center, BorderLayout.CENTER);
            updateColor();
        }

        private void fromHex() {
            try {
                String h = hex.getText().trim().replace("#", "");
                if (h.length() == 3) {
                    h = "" + h.charAt(0) + h.charAt(0) + h.charAt(1) + h.charAt(1) + h.charAt(2) + h.charAt(2);
                }
                int value = Integer.parseInt(h, 16);
                red.setValue((value >> 16) & 255);
                green.setValue((value >> 8) & 255);
                blue.setValue(value & 255);
                updateColor();
            } catch (Exception ex) {
                result.setText("Invalid HEX color.");
            }
        }

        private void updateColor() {
            Color color = new Color(red.getValue(), green.getValue(), blue.getValue());
            swatch.setBackground(color);
            String h = String.format("#%02X%02X%02X", color.getRed(), color.getGreen(), color.getBlue());
            hex.setText(h);
            result.setText(h + " | rgb(" + color.getRed() + ", " + color.getGreen() + ", " + color.getBlue() + ")");
        }

        private class ChangeForwarder implements javax.swing.event.ChangeListener {
            public void stateChanged(javax.swing.event.ChangeEvent e) {
                updateColor();
            }
        }
    }

    private static class FilePanel extends JPanel {
        private JTextArea output = new JTextArea(18, 80);

        FilePanel() {
            super(new BorderLayout(12, 12));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            output.setEditable(false);
            JPanel buttons = new JPanel(new FlowLayout(FlowLayout.LEFT));
            addButton(buttons, "File info", new Runnable() { public void run() { fileInfo(); } });
            addButton(buttons, "Checksum", new Runnable() { public void run() { checksum(); } });
            addButton(buttons, "Copy", new Runnable() { public void run() { copy(output.getText()); } });
            add(buttons, BorderLayout.NORTH);
            add(scroll(output), BorderLayout.CENTER);
        }

        private File pick() {
            JFileChooser chooser = new JFileChooser();
            return chooser.showOpenDialog(this) == JFileChooser.APPROVE_OPTION ? chooser.getSelectedFile() : null;
        }

        private void fileInfo() {
            File f = pick();
            if (f == null) return;
            output.setText("Name: " + f.getName()
                    + "\nPath: " + f.getAbsolutePath()
                    + "\nSize: " + formatBytes(f.length())
                    + "\nLast modified: " + LocalDateTime.ofInstant(new java.util.Date(f.lastModified()).toInstant(), java.time.ZoneId.systemDefault()).format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)
                    + "\nReadable: " + f.canRead()
                    + "\nWritable: " + f.canWrite());
        }

        private void checksum() {
            File f = pick();
            if (f == null) return;
            try {
                output.setText(hashReport(f));
            } catch (Exception ex) {
                output.setText("Could not checksum file: " + ex.getMessage());
            }
        }
    }

    private static class NotesPanel extends JPanel {
        NotesPanel() {
            super(new BorderLayout(12, 12));
            setBorder(new EmptyBorder(18, 18, 18, 18));
            JTextArea notes = new JTextArea();
            notes.setText("Scratchpad\n\nUse this as a quick local note area while working. Nothing is sent anywhere.");
            add(scroll(notes), BorderLayout.CENTER);
            JPanel buttons = new JPanel(new FlowLayout(FlowLayout.LEFT));
            addButton(buttons, "Timestamp", new Runnable() {
                public void run() {
                    notes.append("\n" + LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME) + " - ");
                }
            });
            addButton(buttons, "Copy", new Runnable() { public void run() { copy(notes.getText()); } });
            add(buttons, BorderLayout.NORTH);
        }
    }

    private static Object[] unit(String label, String factor) {
        return new Object[]{label, new BigDecimal(factor, MC)};
    }

    private static void addTable(String name, String note, Object[]... units) {
        LinkedHashMap<String, BigDecimal> table = new LinkedHashMap<String, BigDecimal>();
        for (Object[] unit : units) {
            table.put((String) unit[0], (BigDecimal) unit[1]);
        }
        UNIT_TABLES.put(name, table);
        UNIT_NOTES.put(name, note);
    }

    private static void addCurrencies() {
        String[][] data = {
                {"AUD", "Australian Dollar"}, {"BGN", "Bulgarian Lev"}, {"BRL", "Brazilian Real"},
                {"CAD", "Canadian Dollar"}, {"CHF", "Swiss Franc"}, {"CNY", "Chinese Yuan"},
                {"CZK", "Czech Koruna"}, {"DKK", "Danish Krone"}, {"EUR", "Euro"},
                {"GBP", "Pound Sterling"}, {"HKD", "Hong Kong Dollar"}, {"HUF", "Hungarian Forint"},
                {"IDR", "Indonesian Rupiah"}, {"ILS", "Israeli Shekel"}, {"INR", "Indian Rupee"},
                {"ISK", "Icelandic Krona"}, {"JPY", "Japanese Yen"}, {"KRW", "South Korean Won"},
                {"MXN", "Mexican Peso"}, {"MYR", "Malaysian Ringgit"}, {"NOK", "Norwegian Krone"},
                {"NZD", "New Zealand Dollar"}, {"PHP", "Philippine Peso"}, {"PLN", "Polish Zloty"},
                {"RON", "Romanian Leu"}, {"SEK", "Swedish Krona"}, {"SGD", "Singapore Dollar"},
                {"THB", "Thai Baht"}, {"TRY", "Turkish Lira"}, {"USD", "US Dollar"},
                {"ZAR", "South African Rand"}
        };
        for (String[] row : data) {
            CURRENCIES.put(row[0], row[1]);
        }
    }

    private static String[] currencyOptions() {
        List<String> options = new ArrayList<String>();
        for (Map.Entry<String, String> entry : CURRENCIES.entrySet()) {
            options.add(entry.getKey() + " - " + entry.getValue());
        }
        return options.toArray(new String[0]);
    }

    private static String codeFromOption(String option) {
        return option.substring(0, 3);
    }

    private static BigDecimal fetchCurrency(BigDecimal amount, String from, String to) throws IOException {
        String url = "https://api.frankfurter.app/latest?amount="
                + URLEncoder.encode(amount.stripTrailingZeros().toPlainString(), "UTF-8")
                + "&from=" + URLEncoder.encode(from, "UTF-8")
                + "&to=" + URLEncoder.encode(to, "UTF-8");
        HttpURLConnection connection = (HttpURLConnection) URI.create(url).toURL().openConnection();
        connection.setRequestMethod("GET");
        connection.setConnectTimeout(12000);
        connection.setReadTimeout(12000);
        int status = connection.getResponseCode();
        if (status < 200 || status >= 300) {
            throw new IOException("HTTP " + status);
        }
        BufferedReader reader = new BufferedReader(new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8));
        StringBuilder json = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            json.append(line);
        }
        reader.close();
        Pattern p = Pattern.compile("\"" + Pattern.quote(to) + "\"\\s*:\\s*(-?\\d+(?:\\.\\d+)?)");
        Matcher m = p.matcher(json.toString());
        if (!m.find()) {
            throw new IOException("Rate missing");
        }
        return new BigDecimal(m.group(1), MC);
    }

    private static JPanel labeled(String label, JComponent component) {
        JPanel panel = new JPanel(new BorderLayout(4, 4));
        panel.setOpaque(false);
        JLabel text = new JLabel(label);
        text.setFont(text.getFont().deriveFont(Font.BOLD));
        panel.add(text, BorderLayout.NORTH);
        panel.add(component, BorderLayout.CENTER);
        return panel;
    }

    private static JPanel wrapButton(String label, JButton button) {
        return labeled(label, button);
    }

    private static JPanel gridPanel(int columns) {
        JPanel panel = new JPanel(new GridLayout(1, columns, 12, 12));
        panel.setOpaque(false);
        return panel;
    }

    private static JLabel resultLabel() {
        JLabel label = new JLabel("Ready");
        label.setFont(label.getFont().deriveFont(Font.BOLD, 20f));
        return label;
    }

    private static JPanel centerResult(JLabel result, JLabel note) {
        JPanel panel = new JPanel(new GridBagLayout());
        panel.setBackground(Color.WHITE);
        panel.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(new Color(220, 228, 238)), new EmptyBorder(30, 30, 30, 30)));
        JPanel inner = new JPanel(new GridLayout(2, 1, 8, 8));
        inner.setOpaque(false);
        result.setHorizontalAlignment(SwingConstants.CENTER);
        note.setHorizontalAlignment(SwingConstants.CENTER);
        inner.add(result);
        inner.add(note);
        panel.add(inner);
        return panel;
    }

    private static JPanel card(String title) {
        JPanel panel = new JPanel(new GridLayout(0, 1, 8, 8));
        panel.setBackground(Color.WHITE);
        panel.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createTitledBorder(title),
                new EmptyBorder(8, 10, 10, 10)));
        return panel;
    }

    private static JScrollPane scroll(JTextArea area) {
        area.setLineWrap(true);
        area.setWrapStyleWord(true);
        area.setFont(new Font(Font.MONOSPACED, Font.PLAIN, 13));
        return new JScrollPane(area);
    }

    private static void addButton(JPanel panel, String label, final Runnable runnable) {
        JButton button = new JButton(label);
        button.setFocusPainted(false);
        button.addActionListener(new AbstractAction() {
            public void actionPerformed(ActionEvent e) {
                runnable.run();
            }
        });
        panel.add(button);
    }

    private static DocumentListener simpleListener(final Runnable runnable) {
        return new DocumentListener() {
            public void insertUpdate(DocumentEvent e) { runnable.run(); }
            public void removeUpdate(DocumentEvent e) { runnable.run(); }
            public void changedUpdate(DocumentEvent e) { runnable.run(); }
        };
    }

    private static String format(BigDecimal value) {
        return DECIMAL.format(value);
    }

    private static String money(double value) {
        return "$" + new DecimalFormat("#,##0.00").format(value);
    }

    private static String titleCase(String input) {
        StringBuilder out = new StringBuilder();
        boolean next = true;
        for (char c : input.toCharArray()) {
            if (Character.isWhitespace(c)) {
                next = true;
                out.append(c);
            } else if (next) {
                out.append(Character.toTitleCase(c));
                next = false;
            } else {
                out.append(Character.toLowerCase(c));
            }
        }
        return out.toString();
    }

    private static String sortLines(String input, boolean reverse) {
        List<String> lines = new ArrayList<String>(Arrays.asList(input.split("\\R", -1)));
        Collections.sort(lines);
        if (reverse) Collections.reverse(lines);
        return join(lines, "\n");
    }

    private static String uniqueLines(String input) {
        List<String> lines = Arrays.asList(input.split("\\R", -1));
        List<String> unique = new ArrayList<String>();
        for (String line : lines) {
            if (!unique.contains(line)) {
                unique.add(line);
            }
        }
        return join(unique, "\n");
    }

    private static String trimLines(String input) {
        List<String> lines = Arrays.asList(input.split("\\R", -1));
        List<String> trimmed = new ArrayList<String>();
        for (String line : lines) {
            trimmed.add(line.trim());
        }
        return join(trimmed, "\n");
    }

    private static String join(List<String> values, String separator) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) out.append(separator);
            out.append(values.get(i));
        }
        return out.toString();
    }

    private static String urlEncode(String text) {
        try {
            return URLEncoder.encode(text, "UTF-8");
        } catch (Exception ex) {
            return "Could not URL encode text.";
        }
    }

    private static String urlDecode(String text) {
        try {
            return java.net.URLDecoder.decode(text, "UTF-8");
        } catch (Exception ex) {
            return "Could not URL decode text.";
        }
    }

    private static String escapeJava(String text) {
        StringBuilder out = new StringBuilder();
        for (char c : text.toCharArray()) {
            switch (c) {
                case '\\':
                    out.append("\\\\");
                    break;
                case '"':
                    out.append("\\\"");
                    break;
                case '\n':
                    out.append("\\n");
                    break;
                case '\r':
                    out.append("\\r");
                    break;
                case '\t':
                    out.append("\\t");
                    break;
                default:
                    out.append(c);
                    break;
            }
        }
        return out.toString();
    }

    private static String unescapeJava(String text) {
        StringBuilder out = new StringBuilder();
        boolean escaping = false;
        for (char c : text.toCharArray()) {
            if (!escaping) {
                if (c == '\\') {
                    escaping = true;
                } else {
                    out.append(c);
                }
                continue;
            }

            switch (c) {
                case 'n':
                    out.append('\n');
                    break;
                case 'r':
                    out.append('\r');
                    break;
                case 't':
                    out.append('\t');
                    break;
                case '"':
                    out.append('"');
                    break;
                case '\\':
                    out.append('\\');
                    break;
                default:
                    out.append(c);
                    break;
            }
            escaping = false;
        }
        if (escaping) {
            out.append('\\');
        }
        return out.toString();
    }

    private static void copy(String text) {
        Toolkit.getDefaultToolkit().getSystemClipboard().setContents(new StringSelection(text), null);
    }

    private static String hashReport(byte[] bytes) {
        return "MD5: " + digest("MD5", bytes)
                + "\nSHA-1: " + digest("SHA-1", bytes)
                + "\nSHA-256: " + digest("SHA-256", bytes)
                + "\nSHA-512: " + digest("SHA-512", bytes);
    }

    private static String hashReport(File file) throws Exception {
        return "File: " + file.getAbsolutePath()
                + "\nSize: " + formatBytes(file.length())
                + "\nMD5: " + digest("MD5", file)
                + "\nSHA-1: " + digest("SHA-1", file)
                + "\nSHA-256: " + digest("SHA-256", file)
                + "\nSHA-512: " + digest("SHA-512", file);
    }

    private static String digest(String algorithm, byte[] bytes) {
        try {
            MessageDigest digest = MessageDigest.getInstance(algorithm);
            return hex(digest.digest(bytes));
        } catch (Exception ex) {
            return "Unavailable";
        }
    }

    private static String digest(String algorithm, File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance(algorithm);
        BufferedInputStream in = new BufferedInputStream(new FileInputStream(file));
        byte[] buffer = new byte[8192];
        int read;
        while ((read = in.read(buffer)) != -1) {
            digest.update(buffer, 0, read);
        }
        in.close();
        return hex(digest.digest());
    }

    private static String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder();
        for (byte b : bytes) {
            out.append(String.format("%02x", b & 0xff));
        }
        return out.toString();
    }

    private static String formatBytes(long bytes) {
        if (bytes < 1024) return bytes + " B";
        double value = bytes;
        String[] units = {"B", "KB", "MB", "GB", "TB", "PB"};
        int index = 0;
        while (value >= 1024 && index < units.length - 1) {
            value /= 1024;
            index++;
        }
        return new DecimalFormat("#,##0.##").format(value) + " " + units[index];
    }
}
