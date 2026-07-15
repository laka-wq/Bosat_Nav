<?php
/*
Plugin Name: Navigator PDF Linker
Description: Sends PDF files to a Vercel-hosted Python API and returns the processed file.
Version: 1.0.0
Author: GitHub Copilot
*/

if (!defined('ABSPATH')) {
    exit;
}

class Navigator_PDF_Linker {
    const OPTION_API_URL = 'navigator_pdf_api_url';
    const OPTION_API_KEY = 'navigator_pdf_api_key';

    public function __construct() {
        add_action('admin_menu', array($this, 'add_settings_page'));
        add_action('admin_init', array($this, 'register_settings'));
        add_shortcode('navigator_pdf_upload', array($this, 'render_upload_form'));
    }

    public function add_settings_page() {
        add_options_page(
            'Navigator PDF Linker',
            'Navigator PDF Linker',
            'manage_options',
            'navigator-pdf-linker',
            array($this, 'render_settings_page')
        );
    }

    public function register_settings() {
        register_setting('navigator_pdf_linker', self::OPTION_API_URL);
        register_setting('navigator_pdf_linker', self::OPTION_API_KEY);
    }

    public function render_settings_page() {
        ?>
        <div class="wrap">
            <h1>Navigator PDF Linker</h1>
            <form method="post" action="options.php">
                <?php settings_fields('navigator_pdf_linker'); ?>
                <table class="form-table">
                    <tr>
                        <th scope="row"><label for="navigator_pdf_api_url">Vercel API URL</label></th>
                        <td><input name="<?php echo esc_attr(self::OPTION_API_URL); ?>" id="navigator_pdf_api_url" type="url" class="regular-text" value="<?php echo esc_attr(get_option(self::OPTION_API_URL, '')); ?>" placeholder="https://your-app.vercel.app/process" /></td>
                    </tr>
                    <tr>
                        <th scope="row"><label for="navigator_pdf_api_key">API Key</label></th>
                        <td><input name="<?php echo esc_attr(self::OPTION_API_KEY); ?>" id="navigator_pdf_api_key" type="password" class="regular-text" value="<?php echo esc_attr(get_option(self::OPTION_API_KEY, '')); ?>" /></td>
                    </tr>
                </table>
                <?php submit_button(); ?>
            </form>
        </div>
        <?php
    }

    public function render_upload_form() {
        ob_start();
        if (!empty($_POST['navigator_pdf_submit'])) {
            echo $this->handle_upload();
        }
        ?>
        <form method="post" enctype="multipart/form-data">
            <p><input type="file" name="navigator_pdf_file" accept="application/pdf" required /></p>
            <p><button type="submit" name="navigator_pdf_submit" value="1">Process PDF</button></p>
        </form>
        <?php
        return ob_get_clean();
    }

    private function handle_upload() {
        if (empty($_FILES['navigator_pdf_file']['tmp_name'])) {
            return '<p>No file selected.</p>';
        }

        $api_url = trim((string) get_option(self::OPTION_API_URL, ''));
        $api_key = trim((string) get_option(self::OPTION_API_KEY, ''));

        if ($api_url === '') {
            return '<p>Please configure the API URL in Settings first.</p>';
        }

        $file = $_FILES['navigator_pdf_file'];
        if (!function_exists('curl_init')) {
            return '<p>cURL is required on the WordPress server for file uploads.</p>';
        }

        $curl_file = curl_file_create($file['tmp_name'], 'application/pdf', $file['name']);
        $ch = curl_init($api_url);

        curl_setopt_array($ch, array(
            CURLOPT_POST => true,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 120,
            CURLOPT_HTTPHEADER => array(
                'X-API-Key: ' . $api_key,
            ),
            CURLOPT_POSTFIELDS => array(
                'file' => $curl_file,
            ),
        ));

        $body = curl_exec($ch);
        $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curl_error = curl_error($ch);
        curl_close($ch);

        if ($body === false) {
            return '<p>Request failed: ' . esc_html($curl_error ?: 'Unknown cURL error') . '</p>';
        }

        if ($status !== 200) {
            return '<p>API error: ' . esc_html($body) . '</p>';
        }

        $upload_dir = wp_upload_dir();
        $filename = sanitize_file_name(pathinfo($file['name'], PATHINFO_FILENAME) . '-navigated.pdf');
        $destination = trailingslashit($upload_dir['path']) . $filename;
        file_put_contents($destination, $body);

        $url = trailingslashit($upload_dir['url']) . $filename;
        return '<p>Processed successfully: <a href="' . esc_url($url) . '" target="_blank" rel="noopener">Download PDF</a></p>';
    }
}

new Navigator_PDF_Linker();