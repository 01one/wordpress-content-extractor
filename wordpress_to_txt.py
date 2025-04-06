import os
import xml.etree.ElementTree as ET
import re
from bs4 import BeautifulSoup
from datetime import datetime

def extract_content_from_wordpress_xml(xml_file_path):
    # Define base directories for different content types
    base_dirs = {
        "publish": "published_posts",
        "draft": "drafts",
        "trash": "trash",
        "page": "pages"
    }
    
    # Create output directories if they don't exist
    for directory in base_dirs.values():
        if not os.path.exists(directory):
            os.makedirs(directory)
    
    # Parse the XML file
    tree = ET.parse(xml_file_path)
    root = tree.getroot()
    
    # WordPress XML uses namespaces
    namespaces = {
        'wp': 'http://wordpress.org/export/1.2/',
        'content': 'http://purl.org/rss/1.0/modules/content/',
        'dc': 'http://purl.org/dc/elements/1.1/',
        'excerpt': 'http://wordpress.org/export/1.2/excerpt/'
    }
    
    # Find all items (posts, pages, etc.)
    items = root.findall('.//item')
    
    # Counters for different content types
    counters = {content_type: 0 for content_type in base_dirs.keys()}
    counters["other"] = 0
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    for item in items:
        try:
            # Get post type (post, page, etc.)
            post_type_elem = item.find('./wp:post_type', namespaces)
            post_type = post_type_elem.text if post_type_elem is not None else "unknown"
            
            # Get post status
            status_elem = item.find('./wp:status', namespaces)
            status = status_elem.text if status_elem is not None else "unknown"
            
            # Determine the output directory based on post type and status
            output_dir = None
            if post_type == 'post':
                if status == 'publish':
                    output_dir = base_dirs["publish"]
                elif status == 'draft':
                    output_dir = base_dirs["draft"]
                elif status == 'trash':
                    output_dir = base_dirs["trash"]
            elif post_type == 'page':
                output_dir = base_dirs["page"]
            
            # Skip processing if we couldn't determine the output directory
            if output_dir is None:
                counters["other"] += 1
                continue
            
            # Extract post data
            title_elem = item.find('./title')
            title = title_elem.text if title_elem is not None and title_elem.text else "Untitled"
            
            # Generate slug from post_name or title
            post_name = item.find('./wp:post_name', namespaces)
            if post_name is not None and post_name.text:
                slug = post_name.text
            else:
                # Generate slug from title
                slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
            
            # Get content
            content_elem = item.find('./content:encoded', namespaces)
            content = content_elem.text if content_elem is not None else ""
            
            # Get excerpt
            excerpt_elem = item.find('./excerpt:encoded', namespaces)
            excerpt = excerpt_elem.text if excerpt_elem is not None else ""
            
            # Get categories and tags
            categories = []
            tags = []
            for cat in item.findall('./category'):
                domain = cat.get('domain')
                cat_name = cat.text
                if cat_name:
                    if domain == 'category':
                        categories.append(cat_name)
                    elif domain == 'post_tag':
                        tags.append(cat_name)
            
            # Get publication date
            pub_date = item.find('./pubDate')
            post_date = pub_date.text if pub_date is not None else current_date
            try:
                # Convert WordPress date format to YYYY-MM-DD
                parsed_date = datetime.strptime(post_date, "%a, %d %b %Y %H:%M:%S %z")
                formatted_date = parsed_date.strftime("%Y-%m-%d")
            except:
                formatted_date = current_date
            
            # Get author
            creator = item.find('./dc:creator', namespaces)
            author = creator.text if creator is not None else "Unknown"
            
            # Get comments status
            comment_status = item.find('./wp:comment_status', namespaces)
            comments_allowed = comment_status.text if comment_status is not None else "closed"
            
            if content:
                # Remove HTML comments while preserving content
                content = remove_all_html_comments(content)
                
                # Process content with BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extract CSS and JavaScript
                system_css_links = []
                system_js_links = []
                inline_css = []
                top_js = []
                bottom_js = []
                
                # Extract CSS links
                for link in soup.find_all('link', rel='stylesheet'):
                    href = link.get('href', '')
                    if href:
                        system_css_links.append(link)
                        link.extract()  # Remove from content
                
                # Extract JS script links (top of document)
                for script in soup.find_all('script', src=True):
                    src = script.get('src', '')
                    if src:
                        system_js_links.append(script)
                        script.extract()  # Remove from content
                
                # Extract inline <style> tags
                for style in soup.find_all('style'):
                    if style.string:
                        inline_css.append(style.string)
                    style.extract()  # Remove from content
                
                # Extract inline <script> tags
                content_elements = soup.find_all(['p', 'div', 'section', 'article', 'main'])
                if content_elements:
                    first_content = content_elements[0]
                    last_content = content_elements[-1]
                    
                    for script in soup.find_all('script'):
                        if not script.has_attr('src') and script.string:
                            # Check if this script appears before the first content element
                            if script.sourceline < first_content.sourceline:
                                top_js.append(script.string)
                            # Check if this script appears after the last content element
                            elif script.sourceline > last_content.sourceline:
                                bottom_js.append(script.string)
                            script.extract()  # Remove from content
                
                # Extract meta description
                meta_description = ""
                meta_tags = soup.find_all('meta', attrs={'name': 'description'})
                if meta_tags:
                    meta_description = meta_tags[0].get('content', '')
                    for tag in meta_tags:
                        tag.extract()  # Remove from content
                elif excerpt:
                    # Use excerpt if available
                    soup_excerpt = BeautifulSoup(excerpt, 'html.parser')
                    meta_description = soup_excerpt.get_text()[:160]
                else:
                    # If no meta description, use the first paragraph or a portion of the content
                    first_p = soup.find('p')
                    if first_p:
                        meta_description = first_p.text[:160]
                    else:
                        # Strip HTML and take first 160 chars
                        plain_text = re.sub(r'<.*?>', '', str(soup)[:300])
                        meta_description = plain_text[:160].strip()
                
                # Get the clean content without the extracted elements
                clean_content = str(soup)
                
                # Prepare numbered content sections
                metadata_lines = [
                    f"slug: {slug}",
                    f"title: {title}",
                    f"description: {meta_description}",
                    f"date: {formatted_date}",
                    f"author: {author}",
                    f"status: {status}",
                    f"type: {post_type}",
                    f"categories: {', '.join(categories)}",
                    f"tags: {', '.join(tags)}",
                    f"comments: {comments_allowed}"
                ]
                
                # Default CSS and script stubs
                default_css = ''
                default_js = ''
                default_end_js = ''
                
                # Add default CSS and JS if none found
                if not system_css_links:
                    system_css_links.append(default_css)
                
                if not system_js_links and not top_js:
                    top_js.append(default_js)
                
                if not bottom_js:
                    bottom_js.append(default_end_js)
                
                # Format metadata section
                metadata_section = []
                metadata_section.append("### METADATA SECTION START ###")
                for line in metadata_lines:
                    metadata_section.append(f" {line}")
                metadata_section.append("### METADATA SECTION END ###")
                
                # Format system CSS section
                css_link_section = []
                css_link_section.append("### SYSTEM CSS SECTION START ###")
                for css_link in system_css_links:
                    css_link_section.append(f" {css_link}")
                css_link_section.append("### SYSTEM CSS SECTION END ###")
                
                # Format inline CSS section
                inline_css_section = []
                inline_css_section.append("### INLINE CSS SECTION START ###")
                for css in inline_css:
                    for css_line in css.split('\n'):
                        inline_css_section.append(f"  {css_line}")
                inline_css_section.append("### INLINE CSS SECTION END ###")
                
                # Format system JS section
                script_link_section = []
                script_link_section.append("### SYSTEM JS LINK SECTION START ###")
                for js_link in system_js_links:
                    script_link_section.append(f" {js_link}")
                script_link_section.append("### SYSTEM JS LINK SECTION END ###")                
                
                # Format top JS section
                top_js_section = []
                top_js_section.append("### TOP JS SECTION START ###")
                for js in top_js:
                    for js_line in js.split('\n'):
                        top_js_section.append(f" {js_line}")
                top_js_section.append("### TOP JS SECTION END ###")
                
                # Format main content
                content_section = []
                content_section.append("### MAIN CONTENT SECTION START ###")
                for content_line in clean_content.split('\n'):
                    content_section.append(f" {content_line}")
                content_section.append("### MAIN CONTENT SECTION END ###")
                
                # Format bottom JS section
                bottom_js_section = []
                bottom_js_section.append("### BOTTOM JS SECTION START ###")
                for js in bottom_js:
                    for js_line in js.split('\n'):
                        bottom_js_section.append(f" {js_line}")
                bottom_js_section.append("### BOTTOM JS SECTION END ###")
                
                # Format system JS bottom section
                system_js_bottom = []
                script_link_bottom_section = []
                script_link_bottom_section.append("### BOTTOM JS LINK SECTION START ###")
                for js_link in system_js_bottom:
                    script_link_bottom_section.append(f" {js_link}")
                script_link_bottom_section.append("### BOTTOM JS LINK SECTION END ###")                       
                
                # Combine all sections
                all_sections = [
                    '\n'.join(metadata_section),
                    '\n'.join(css_link_section),
                    '\n'.join(inline_css_section),
                    '\n'.join(script_link_section),
                    '\n'.join(top_js_section),
                    '\n'.join(content_section),
                    '\n'.join(bottom_js_section),
                    '\n'.join(script_link_bottom_section)
                ]
                
                formatted_content = '\n\n'.join(all_sections)
                
                # Save to file
                file_path = os.path.join(output_dir, f"{slug}.txt")
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(formatted_content)
                
                # Update counter
                if post_type == 'post':
                    if status == 'publish':
                        counters["publish"] += 1
                    elif status == 'draft':
                        counters["draft"] += 1
                    elif status == 'trash':
                        counters["trash"] += 1
                elif post_type == 'page':
                    counters["page"] += 1
                
                print(f"Processed {post_type} ({status}): {title} -> {file_path}")
        
        except Exception as e:
            print(f"Error processing item: {e}")
    
    # Print summary
    print("\nExtraction Summary:")
    print(f"Published Posts: {counters['publish']}")
    print(f"Draft Posts: {counters['draft']}")
    print(f"Trash Posts: {counters['trash']}")
    print(f"Pages: {counters['page']}")
    print(f"Others/Skipped: {counters['other']}")


def remove_all_html_comments(html_content):
    """
    Remove all HTML comments from content.
    """
    if not html_content:
        return ""
        
    # Use BeautifulSoup to parse and remove comments
    soup = BeautifulSoup(html_content, 'html.parser')
    comments = soup.find_all(string=lambda text: isinstance(text, str) and text.strip().startswith('<!--'))
    
    for comment in comments:
        comment.extract()
    
    # Convert back to string
    cleaned_html = str(soup)
    
    # In case BeautifulSoup missed some comments, apply regex as backup
    cleaned_html = re.sub(r'<!--[\s\S]*?-->', '', cleaned_html)
    
    return cleaned_html


if __name__ == "__main__":
    # Path to your WordPress XML export file
    xml_file_path = "your_website_wordpress_export.xml"
    
    # Extract posts
    extract_content_from_wordpress_xml(xml_file_path)
