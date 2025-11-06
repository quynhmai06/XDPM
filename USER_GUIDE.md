# 📘 Hướng dẫn sử dụng nền tảng XDPM

## 🚀 Giới thiệu

XDPM là nền tảng giao dịch xe điện và pin cũ trực tuyến, kết nối người mua và người bán trên toàn quốc.

---

## 1. 🔐 Đăng ký & Đăng nhập

### Đăng ký tài khoản mới

1. Truy cập: http://localhost:8000/register
2. Điền thông tin:
   - Username (tên đăng nhập)
   - Email
   - Mật khẩu
   - Số điện thoại
3. Nhấn "Đăng ký"

### Đăng nhập

1. Truy cập: http://localhost:8000/login
2. Nhập username và password
3. Nhấn "Đăng nhập"

---

## 2. 🔍 Tìm kiếm sản phẩm

### Tìm kiếm đơn giản (Trang chủ)

1. Chọn loại sản phẩm: **Xe điện** hoặc **Pin**
2. Nhấn nút **"Tìm kiếm"**
3. Mở bộ lọc nâng cao

### Tìm kiếm nâng cao

1. Chọn tab: **Xe điện** hoặc **Pin điện**
2. Điền các tiêu chí:
   - **Hãng xe/pin**: VinFast, BYD, MG, v.v.
   - **Năm sản xuất**: Từ năm - Đến năm
   - **Giá**: Từ - Đến
   - **Quãng đường**: Số km đã chạy
   - **Dung lượng pin**: kWh
   - **Tỉnh/Thành**: Chọn địa phương
3. Nhấn **"Tìm kiếm"**
4. Xem kết quả hiển thị bên dưới

---

## 3. 🛒 Mua sản phẩm

### Cách 1: Mua ngay (Nhanh nhất)

1. Vào trang chi tiết sản phẩm (click vào card sản phẩm)
2. Xem thông tin chi tiết (ảnh, mô tả, giá, thông số)
3. Nhấn nút **"⚡ Mua ngay"**
4. Tự động chuyển đến trang thanh toán
5. Điền thông tin giao hàng
6. Chọn phương thức thanh toán:
   - COD (Thanh toán khi nhận hàng)
   - Chuyển khoản ngân hàng
   - Ví điện tử
7. Nhấn **"Đặt hàng ngay"**
8. Hoàn tất! Kiểm tra email xác nhận

### Cách 2: Thêm vào giỏ hàng (Mua nhiều sản phẩm)

1. Vào trang chi tiết sản phẩm
2. Nhấn nút **"🛒 Thêm vào giỏ hàng"**
3. Tiếp tục mua sắm hoặc vào giỏ hàng
4. Tại giỏ hàng (`/cart`):
   - Xem lại sản phẩm đã chọn
   - Cập nhật số lượng
   - Xóa sản phẩm không muốn mua
5. Nhấn **"Tiến hành thanh toán"**
6. Thực hiện các bước như Cách 1 (từ bước 5)

---

## 4. 🔨 Đấu giá

### Xem phiên đấu giá

1. **Trang chủ**: Kéo xuống section "Phiên đấu giá đang diễn ra"
2. **Trang đấu giá**: Truy cập `/auctions`
3. Thông tin hiển thị:
   - Tên sản phẩm
   - Giá khởi điểm
   - Giá hiện tại (giá đặt cao nhất)
   - Thời gian kết thúc
   - Trạng thái (Đang mở / Đã đóng)

### Tham gia đấu giá

1. Click vào phiên đấu giá muốn tham gia
2. Xem chi tiết sản phẩm và lịch sử đặt giá
3. Nhập giá đặt (phải cao hơn giá hiện tại)
4. Nhấn **"Đặt giá"**
5. Nếu giá của bạn cao nhất → Bạn đang dẫn đầu
6. Khi phiên kết thúc → Người đặt giá cao nhất thắng

### Mua ngay (Buy Now) trong đấu giá

1. Nếu người bán đặt giá "Mua ngay"
2. Nhấn nút **"💰 Mua ngay"**
3. Phiên đấu giá đóng ngay lập tức
4. Sản phẩm được thêm vào giỏ hàng
5. Tiến hành thanh toán như mua thông thường

### Tạo phiên đấu giá (Người bán)

1. Truy cập: `/auctions/create`
2. Chọn sản phẩm muốn đấu giá (từ tin đã đăng)
3. Điền thông tin:
   - **Giá khởi điểm**: Giá bắt đầu đấu giá
   - **Giá mua ngay** (tùy chọn): Giá mua ngay lập tức
   - **Thời gian kết thúc**: Chọn ngày giờ
4. Nhấn **"Tạo phiên đấu giá"**
5. Phiên đấu giá sẽ hiển thị ở trang chủ và trang `/auctions`

---

## 5. ❤️ Yêu thích & So sánh

### Thêm vào yêu thích

1. **Từ card sản phẩm** (trang chủ):
   - Click nút **❤️** ở góc phải trên
2. **Từ trang chi tiết**:
   - Nhấn nút **"❤️ Yêu thích"**
3. Sản phẩm được lưu vào `/favorites`

### Xem danh sách yêu thích

1. Truy cập: `/favorites`
2. Xem tất cả sản phẩm đã lưu
3. Click **"Xóa"** để bỏ khỏi yêu thích
4. Click **"Xem chi tiết"** để xem sản phẩm

### So sánh sản phẩm

1. Vào trang Yêu thích (`/favorites`)
2. Tích chọn **2-5 sản phẩm** muốn so sánh
   - ⚠️ Chỉ chọn sản phẩm cùng loại (tất cả là xe HOẶC tất cả là pin)
3. Nhấn nút **"⚖️ So sánh"**
4. Xem bảng so sánh chi tiết:
   - Hình ảnh
   - Giá
   - Thông số kỹ thuật
   - Mô tả
5. Click **"Xóa"** để bỏ sản phẩm khỏi danh sách so sánh

---

## 6. 📝 Đăng tin bán

### Đăng tin mới

1. Truy cập: `/listings/new`
2. Chọn loại: **Xe điện** hoặc **Pin**
3. Điền thông tin:
   - **Tên sản phẩm**
   - **Hãng**
   - **Năm sản xuất**
   - **Giá bán**
   - **Tỉnh/Thành**
   - **Quãng đường đã chạy** (xe)
   - **Dung lượng pin** (kWh)
   - **Mô tả chi tiết**
4. Upload ảnh sản phẩm (ảnh chính + ảnh phụ)
5. Sử dụng **AI gợi ý giá** (nếu muốn):
   - Nhấn nút "AI gợi ý giá"
   - Hệ thống sẽ đưa ra mức giá hợp lý dựa trên:
     - Năm sản xuất
     - Quãng đường
     - Dung lượng pin
     - Hãng xe
     - Khu vực
6. Nhấn **"Đăng tin"**
7. Chờ Admin duyệt → Tin sẽ hiển thị công khai

### Quản lý tin đã đăng

1. Vào trang cá nhân
2. Xem danh sách tin đã đăng
3. Chỉnh sửa hoặc xóa tin

---

## 7. 📦 Quản lý đơn hàng

### Xem lịch sử mua

1. Truy cập: `/transactions`
2. Tab **"Đơn hàng của tôi"** (Buyer)
3. Xem:
   - Mã đơn hàng
   - Sản phẩm đã mua
   - Tổng tiền
   - Trạng thái (Đang xử lý / Đã giao / Đã hủy)
   - Ngày đặt

### Xem lịch sử bán

1. Truy cập: `/transactions`
2. Tab **"Tin tôi bán"** (Seller)
3. Xem:
   - Đơn hàng từ người mua
   - Thông tin người mua
   - Sản phẩm
   - Trạng thái giao hàng

---

## 8. ⭐ Đánh giá

### Đánh giá sản phẩm/người bán

1. Truy cập: `/reviews`
2. Sau khi nhận hàng → Viết đánh giá:
   - **Số sao**: 1-5 sao
   - **Nội dung**: Chia sẻ trải nghiệm
   - **Ảnh** (nếu có)
3. Nhấn **"Gửi đánh giá"**

### Xem đánh giá

- Trên trang chi tiết sản phẩm
- Trên trang cá nhân người bán

---

## 9. 👤 Quản lý tài khoản

### Xem thông tin cá nhân

1. Truy cập: `/profile`
2. Xem:
   - Tên
   - Email
   - Số điện thoại
   - Avatar
   - Số tin đã đăng
   - Đánh giá từ người mua

### Chỉnh sửa thông tin

1. Truy cập: `/profile/edit`
2. Cập nhật:
   - Tên hiển thị
   - Email
   - Số điện thoại
   - Avatar (upload ảnh mới)
3. Nhấn **"Lưu thay đổi"**

### Đổi mật khẩu

1. Vào trang chỉnh sửa profile
2. Nhập:
   - Mật khẩu cũ
   - Mật khẩu mới
   - Xác nhận mật khẩu mới
3. Nhấn **"Đổi mật khẩu"**

---

## 10. 📱 Menu điều hướng

### Header Menu

- **Trang chủ**: Xem sản phẩm mới, đấu giá
- **Chính sách**: Điều khoản sử dụng
- **Đấu giá**: Danh sách phiên đấu giá
- **Yêu thích**: Sản phẩm đã lưu
- **Đánh giá**: Xem và viết review
- **Giao dịch**: Lịch sử mua/bán
- **Giỏ hàng**: Xem giỏ hàng
- **Thanh toán**: Checkout

### User Menu (Khi đã đăng nhập)

- **Hồ sơ**: Xem thông tin cá nhân
- **Đăng tin**: Đăng tin bán sản phẩm
- **Đấu giá**: Tạo phiên đấu giá
- **Đăng xuất**: Thoát tài khoản

---

## 💡 Mẹo sử dụng

### Mua hàng an toàn

- ✅ Kiểm tra đánh giá người bán
- ✅ Đọc kỹ mô tả sản phẩm
- ✅ Xem đầy đủ ảnh
- ✅ Hỏi thêm thông tin qua chat
- ✅ Chọn COD nếu muốn kiểm tra hàng trước khi trả tiền

### Bán hàng hiệu quả

- ✅ Chụp ảnh sản phẩm rõ nét, đầy đủ góc độ
- ✅ Viết mô tả chi tiết, trung thực
- ✅ Đặt giá hợp lý (dùng AI gợi ý giá)
- ✅ Phản hồi nhanh tin nhắn từ người mua
- ✅ Cung cấp đầy đủ giấy tờ xe/pin

### Tối ưu tìm kiếm

- 🔍 Sử dụng bộ lọc nâng cao để tìm chính xác
- 🔍 Lưu sản phẩm vào Yêu thích để theo dõi
- 🔍 So sánh 2-5 sản phẩm trước khi quyết định mua

### Đấu giá thông minh

- 💰 Đặt giá tối đa sẵn sàng trả
- 💰 Theo dõi thời gian còn lại
- 💰 Sử dụng "Mua ngay" nếu giá hợp lý
- 💰 Đọc kỹ điều khoản đấu giá

---

## 🆘 Hỗ trợ

### Liên hệ

- **Email**: support@xdpm.vn
- **Hotline**: 1900-xxxx
- **Chat**: Sử dụng chat box ở góc phải màn hình

### FAQ

- Trang chủ → Chính sách → Câu hỏi thường gặp

---

**Phiên bản**: 1.0.0  
**Cập nhật**: November 3, 2025  
**Nền tảng**: XDPM - EV Trading Platform
