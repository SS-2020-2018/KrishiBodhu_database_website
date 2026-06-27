from flask import Flask, render_template, request, redirect, url_for, session, flash
import oracledb

oracledb.init_oracle_client()

app = Flask(__name__)
app.secret_key = 'agroequip_secret_key'

def db_connection():
    return oracledb.connect(user="system", password="2k22", dsn="localhost:1521/xe")

def row_to_dict(cursor, row):
    return {col[0].lower(): 
                    val for col, 
                    val in zip(cursor.description, row)
            }

@app.route('/')
def index():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    sort_by = request.args.get('sort_by', '').strip()
    having_min_count = request.args.get('having_min_count', '').strip()
    set_operation = request.args.get('set_operation', '').strip()
    
    query_a = f"""
        SELECT e.equipment_id, e.seller_id, e.title, e.category, e.price, e.stock_quantity, e.description,
               u.name AS seller_name, u.email AS seller_email
        FROM equipment e
        INNER JOIN users u ON e.seller_id = u.user_id
        WHERE e.stock_quantity > 0
    """
    params = {}
    
    if search:
        query_a += " AND (UPPER(e.title) LIKE :search OR UPPER(e.description) LIKE :search)"
        params['search'] = f"%{search.upper()}%"
    if category:
        query_a += " AND e.category = :category"
        params['category'] = category
    if min_price:
        try:
            query_a += " AND e.price >= :min_price"
            params['min_price'] = float(min_price)
        except ValueError: pass
    if max_price:
        try:
            query_a += " AND e.price <= :max_price"
            params['max_price'] = float(max_price)
        except ValueError: pass

    final_query = query_a
    
    if set_operation in ['UNION', 'INTERSECT', 'MINUS']:
        query_b = """
            SELECT e.equipment_id, e.seller_id, e.title, e.category, e.price, e.stock_quantity, e.description,
                   u.name AS seller_name, u.email AS seller_email
            FROM equipment e
            INNER JOIN users u ON e.seller_id = u.user_id
            WHERE e.price < 1000 AND e.stock_quantity > 0
        """
        final_query = f"({query_a}) {set_operation} ({query_b})"
        

    if sort_by == 'alpha_asc':
        final_query += " ORDER BY UPPER(title) ASC"
    elif sort_by == 'alpha_desc':
        final_query += " ORDER BY UPPER(title) DESC"
    else:
        final_query += " ORDER BY equipment_id DESC"
    

    conn = db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(final_query, params)
        raw_items = cursor.fetchall()
        items = [row_to_dict(cursor, r) for r in raw_items]
    except oracledb.DatabaseError as e:
        print(f"Set Operation Error: {e}")
        items = []

    
    stats_query = "SELECT category, COUNT(equipment_id) AS total_listings, SUM(stock_quantity) AS stock_sum, AVG(price) AS price_avg FROM equipment WHERE stock_quantity > 0"
    stats_params = {}
    
    if search:
        stats_query += " AND (UPPER(title) LIKE :search OR UPPER(description) LIKE :search)"
        stats_params['search'] = f"%{search.upper()}%"
    if category:
        stats_query += " AND category = :category"
        stats_params['category'] = category
        
    stats_query += " GROUP BY category"
    
    if having_min_count:
        try:
            stats_query += " HAVING COUNT(equipment_id) >= :min_count"
            stats_params['min_count'] = int(having_min_count)
        except ValueError: pass
            
    stats_query += " ORDER BY category ASC"
    
    cursor.execute(stats_query, stats_params)
    raw_stats = cursor.fetchall()
    aggregates_summary = [row_to_dict(cursor, r) for r in raw_stats]
    
    cursor.close()
    conn.close()
    return render_template('index.html', items=items, aggregates_summary=aggregates_summary)

@app.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    total = sum(float(item['subtotal']) for item in cart_items) if cart_items else 0.0
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/add_to_cart/<int:equipment_id>')
def add_to_cart(equipment_id):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equipment WHERE equipment_id = :id", {'id': equipment_id})
    row = cursor.fetchone()
    
    if row:
        item = row_to_dict(cursor, row)
        if 'cart' not in session:
            session['cart'] = []
            
        cart_list = session['cart']
        found = False
        for c_item in cart_list:
            if c_item['equipment_id'] == equipment_id:
                c_item['quantity'] += 1
                c_item['subtotal'] = c_item['quantity'] * float(c_item['price'])
                found = True
                break
                
        if not found:
            cart_list.append({
                'equipment_id': item['equipment_id'],
                'title': item['title'],
                'category': item['category'],
                'price': float(item['price']),
                'quantity': 1,
                'subtotal': float(item['price'])
            })
            
        session['cart'] = cart_list
        flash(f"'{item['title']}' added to cart matrix successfully!", "success")
        
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'cart' in session:
        session.pop('cart')
        flash("Stored Transaction Procedure Executed Successfully!", "success")
    else:
        flash("Your cart matrix is empty.", "error")
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        conn = db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (user_id, name, email, password, role) 
                VALUES (user_seq.NEXTVAL, :name, :email, :password, :role)
            """, {'name': name, 'email': email, 'password': password, 'role': role})
            conn.commit()
            flash("Registration Successful! Please log in.")
            return redirect(url_for('login'))
        except oracledb.DatabaseError as e:
            flash("Error processing configuration parameters.")
            print(e)
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = :email AND password = :password", 
                       {'email': email, 'password': password})
        row = cursor.fetchone()
        
        if row:
            user = row_to_dict(cursor, row)
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            
            if session['user_role'] == 'seller':
                return redirect(url_for('seller_dashboard'))
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password.")
        cursor.close()
        conn.close()
    return render_template('login.html')

@app.route('/seller_dashboard', methods=['GET', 'POST'])
def seller_dashboard():
    if 'user_role' not in session or session['user_role'] != 'seller':
        return redirect(url_for('login'))
        
    conn = db_connection()
    cursor = conn.cursor()
    
    
    if request.method == 'POST':
        equipment_id = request.form.get('equipment_id', '').strip()
        title = request.form['title']
        category = request.form['category']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        description = request.form['description']
        
        if equipment_id:
            
            update_query = """
                UPDATE equipment 
                SET title = :title, 
                    category = :category, 
                    price = :price, 
                    stock_quantity = :stock, 
                    description = :description
                WHERE equipment_id = :equipment_id AND seller_id = :seller_id
            """
            cursor.execute(update_query, {
                'title': title, 
                'category': category, 
                'price': price, 
                'stock': stock, 
                'description': description, 
                'equipment_id': int(equipment_id),
                'seller_id': session['user_id']
            })
            conn.commit()
            flash("SQL UPDATE SET operation completed successfully!", "success")
        else:
          
            cursor.execute("""
                INSERT INTO equipment (equipment_id, seller_id, title, category, price, stock_quantity, description)
                VALUES (equip_seq.NEXTVAL, :seller_id, :title, :category, :price, :stock, :description)
            """, {'seller_id': session['user_id'], 'title': title, 'category': category, 'price': price, 'stock': stock, 'description': description})
            conn.commit()
            flash("New item schema inserted successfully!", "success")
        

    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    
    query = """
        SELECT e.equipment_id, e.seller_id, e.title, e.category, e.price, e.stock_quantity, e.description,
               u.name AS seller_name, u.email AS seller_email
        FROM equipment e
        INNER JOIN users u ON e.seller_id = u.user_id
        WHERE e.seller_id = :seller_id
    """
    params = {'seller_id': session['user_id']}
    
    if search:
        query += " AND (UPPER(e.title) LIKE :search OR UPPER(e.description) LIKE :search)"
        params['search'] = f"%{search.upper()}%"
        
    if category:
        query += " AND e.category = :category"
        params['category'] = category
        
    query += " ORDER BY e.equipment_id ASC"
    
    cursor.execute(query, params)
    raw_inventory = cursor.fetchall()
    inventory = [row_to_dict(cursor, r) for r in raw_inventory]
    cursor.close()
    conn.close()
    return render_template('seller_dashboard.html', inventory=inventory)
@app.route('/delete_equipment/<int:equipment_id>', methods=['POST'])
def delete_equipment(equipment_id):
    if 'user_role' not in session or session['user_role'] != 'seller':
        return redirect(url_for('login'))
        
    conn = db_connection()
    cursor = conn.cursor()
    try:
        
        cursor.execute("""
            DELETE FROM equipment 
            WHERE equipment_id = :equipment_id AND seller_id = :seller_id
        """, {'equipment_id': equipment_id, 'seller_id': session['user_id']})
        conn.commit()
        flash("SQL DELETE operation executed successfully! Item removed from database matrix.", "success")
    except oracledb.DatabaseError as e:
        print(f"Deletion Sequence Failure: {e}")
        flash("Error executing database deletion sequence.", "error")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('seller_dashboard'))
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=2026)